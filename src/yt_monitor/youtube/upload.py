"""YouTube OAuth 연결과 재개 가능한 비공개 영상 업로드 작업."""

from __future__ import annotations

import json
import mimetypes
import os
import random
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Literal, Mapping, Optional, Protocol, cast

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

YOUTUBE_UPLOAD_SCOPE: str = "https://www.googleapis.com/auth/youtube.upload"
DEFAULT_YOUTUBE_REDIRECT_URI: str = "http://localhost:8088/api/youtube/oauth/callback"
DEFAULT_YOUTUBE_CLIENT_SECRETS_FILE: str = "/run/secrets/youtube-client.json"
DEFAULT_YOUTUBE_TOKEN_FILE: str = "/app/data/youtube-oauth/token.json"
OAUTH_STATE_TTL_SECONDS: float = 600.0
UPLOAD_CHUNK_SIZE_BYTES: int = 8 * 1024 * 1024

UploadStatus = Literal["queued", "running", "done", "failed", "cancelled"]
CancelResult = Literal["accepted", "not_found", "not_cancellable"]

UPLOAD_SOURCE_DIRECTORIES: frozenset[str] = frozenset(
    {"merged", "split", "uploads", "web_downloads"}
)
UPLOAD_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ts", ".webm"}
)
_RETRIABLE_HTTP_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})
_UPLOAD_URL_PATTERN = re.compile(r"https://www\.googleapis\.com/upload/\S+")


class OAuthConfigurationError(RuntimeError):
    """OAuth client configuration is missing or invalid."""


class OAuthStateError(RuntimeError):
    """OAuth callback state is missing, expired, mismatched, or replayed."""


class OAuthConnectionError(RuntimeError):
    """OAuth token exchange or stored connection failed."""


@dataclass(frozen=True)
class YouTubeOAuthStatusDTO:
    configured: bool
    connected: bool


@dataclass(frozen=True)
class YouTubeUploadMetadataDTO:
    title: str
    description: str
    tags: List[str]
    category_id: str
    made_for_kids: bool


@dataclass
class YouTubeUploadJobDTO:
    id: str
    source: str
    title: str
    status: UploadStatus
    bytes_uploaded: int
    total_bytes: int
    progress_percent: float
    message: str
    started_at: float
    finished_at: Optional[float]
    elapsed_seconds: float
    video_id: Optional[str]
    video_url: Optional[str]
    cancel_requested: bool


@dataclass(frozen=True)
class _OAuthClientConfigDTO:
    client_id: str
    client_secret: str
    token_uri: str
    redirect_uris: List[str]


@dataclass(frozen=True)
class _OAuthStateEntry:
    flow: Flow
    expires_at: float


class UploadProgressProtocol(Protocol):
    resumable_progress: int


class UploadRequestProtocol(Protocol):
    def next_chunk(
        self, num_retries: int = 0
    ) -> tuple[Optional[UploadProgressProtocol], Optional[Mapping[str, object]]]: ...


class YouTubeUploadRequestFactoryProtocol(Protocol):
    def is_connected(self) -> bool: ...

    def create_request(
        self,
        source_path: Path,
        metadata: YouTubeUploadMetadataDTO,
    ) -> UploadRequestProtocol: ...


class _VideosInsertProtocol(Protocol):
    def insert(
        self,
        *,
        part: str,
        body: Mapping[str, object],
        media_body: MediaFileUpload,
        notifySubscribers: bool,
    ) -> UploadRequestProtocol: ...


class _YouTubeServiceProtocol(Protocol):
    def videos(self) -> _VideosInsertProtocol: ...


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OAuthConfigurationError("OAuth 설정 파일을 읽을 수 없습니다") from error
    if not isinstance(loaded, dict):
        raise OAuthConfigurationError("OAuth 설정 파일 형식이 올바르지 않습니다")
    return cast(Mapping[str, object], loaded)


def _read_client_config(path: Path) -> _OAuthClientConfigDTO:
    document = _read_json_object(path)
    raw_web = document.get("web")
    if not isinstance(raw_web, dict):
        raise OAuthConfigurationError("Web application OAuth client가 필요합니다")
    web = cast(Mapping[str, object], raw_web)

    client_id = web.get("client_id")
    client_secret = web.get("client_secret")
    token_uri = web.get("token_uri")
    raw_redirect_uris = web.get("redirect_uris")
    if (
        not isinstance(client_id, str)
        or not client_id
        or not isinstance(client_secret, str)
        or not client_secret
        or not isinstance(token_uri, str)
        or not token_uri
        or not isinstance(raw_redirect_uris, list)
        or not all(isinstance(uri, str) for uri in raw_redirect_uris)
    ):
        raise OAuthConfigurationError("OAuth client 필수 값이 누락되었습니다")

    return _OAuthClientConfigDTO(
        client_id=client_id,
        client_secret=client_secret,
        token_uri=token_uri,
        redirect_uris=cast(List[str], raw_redirect_uris),
    )


def _atomic_write_token(path: Path, refresh_token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass

    temporary_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    payload = {
        "version": 1,
        "refresh_token": refresh_token,
        "scopes": [YOUTUBE_UPLOAD_SCOPE],
    }
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _read_refresh_token(path: Path) -> str:
    try:
        document = _read_json_object(path)
    except OAuthConfigurationError as error:
        raise OAuthConnectionError(
            "저장된 YouTube 연결 정보를 읽을 수 없습니다"
        ) from error
    version = document.get("version")
    refresh_token = document.get("refresh_token")
    scopes = document.get("scopes")
    if (
        version != 1
        or not isinstance(refresh_token, str)
        or not refresh_token
        or not isinstance(scopes, list)
        or YOUTUBE_UPLOAD_SCOPE not in scopes
    ):
        raise OAuthConnectionError("저장된 YouTube 연결 정보가 올바르지 않습니다")
    return refresh_token


def _revoke_google_token(refresh_token: str) -> None:
    encoded = urllib.parse.urlencode({"token": refresh_token}).encode("ascii")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/revoke",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        return


class YouTubeOAuthManager:
    """Single-account OAuth state and minimal refresh-token persistence."""

    def __init__(
        self,
        client_secrets_file: Path,
        token_file: Path,
        redirect_uri: str,
        state_ttl_seconds: float = OAUTH_STATE_TTL_SECONDS,
        token_revoker: Callable[[str], None] = _revoke_google_token,
    ):
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.redirect_uri = redirect_uri
        self.state_ttl_seconds = state_ttl_seconds
        self._token_revoker = token_revoker
        self._states: Dict[str, _OAuthStateEntry] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls) -> YouTubeOAuthManager:
        return cls(
            client_secrets_file=Path(
                os.environ.get(
                    "YT_YOUTUBE_CLIENT_SECRETS_FILE",
                    DEFAULT_YOUTUBE_CLIENT_SECRETS_FILE,
                )
            ),
            token_file=Path(
                os.environ.get("YT_YOUTUBE_TOKEN_FILE", DEFAULT_YOUTUBE_TOKEN_FILE)
            ),
            redirect_uri=os.environ.get(
                "YT_YOUTUBE_REDIRECT_URI", DEFAULT_YOUTUBE_REDIRECT_URI
            ),
        )

    def status(self) -> YouTubeOAuthStatusDTO:
        try:
            client_config = _read_client_config(self.client_secrets_file)
            configured = self.redirect_uri in client_config.redirect_uris
        except OAuthConfigurationError:
            return YouTubeOAuthStatusDTO(configured=False, connected=False)

        connected = False
        if configured and self.token_file.is_file():
            try:
                _read_refresh_token(self.token_file)
                connected = True
            except OAuthConnectionError:
                connected = False
        return YouTubeOAuthStatusDTO(configured=configured, connected=connected)

    def start_authorization(self) -> tuple[str, str]:
        status = self.status()
        if not status.configured:
            raise OAuthConfigurationError(
                "YouTube OAuth client 또는 redirect URI가 설정되지 않았습니다"
            )

        state = secrets.token_urlsafe(32)
        flow = Flow.from_client_secrets_file(
            str(self.client_secrets_file),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
            state=state,
        )
        flow.redirect_uri = self.redirect_uri
        authorization_url, returned_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        if returned_state != state:
            raise OAuthConnectionError("OAuth state 생성에 실패했습니다")

        with self._lock:
            self._remove_expired_states_locked()
            self._states[state] = _OAuthStateEntry(
                flow=flow,
                expires_at=time.monotonic() + self.state_ttl_seconds,
            )
        return authorization_url, state

    def consume_state(
        self,
        request_state: Optional[str],
        cookie_state: Optional[str],
    ) -> Flow:
        with self._lock:
            self._remove_expired_states_locked()
            entry = self._states.pop(request_state, None) if request_state else None

        if (
            not request_state
            or not cookie_state
            or not secrets.compare_digest(request_state, cookie_state)
            or entry is None
        ):
            raise OAuthStateError("OAuth state가 올바르지 않거나 만료되었습니다")
        return entry.flow

    def finish_authorization(self, flow: Flow, code: Optional[str]) -> None:
        if not code:
            raise OAuthConnectionError("OAuth authorization code가 없습니다")
        try:
            flow.fetch_token(code=code)
        except Exception as error:
            raise OAuthConnectionError("Google 계정 연결에 실패했습니다") from error

        refresh_token = flow.credentials.refresh_token
        if not refresh_token:
            raise OAuthConnectionError("Google refresh token을 받지 못했습니다")
        _atomic_write_token(self.token_file, refresh_token)

    def credentials(self) -> Credentials:
        client_config = _read_client_config(self.client_secrets_file)
        if self.redirect_uri not in client_config.redirect_uris:
            raise OAuthConfigurationError("OAuth redirect URI가 등록되지 않았습니다")
        refresh_token = _read_refresh_token(self.token_file)
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=client_config.token_uri,
            client_id=client_config.client_id,
            client_secret=client_config.client_secret,
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )

    def disconnect(self) -> None:
        refresh_token: Optional[str] = None
        if self.token_file.is_file():
            try:
                refresh_token = _read_refresh_token(self.token_file)
            except OAuthConnectionError:
                refresh_token = None
        try:
            if refresh_token:
                self._token_revoker(refresh_token)
        except Exception:
            pass
        finally:
            self.token_file.unlink(missing_ok=True)

    def _remove_expired_states_locked(self) -> None:
        now = time.monotonic()
        expired_states = [
            state for state, entry in self._states.items() if entry.expires_at <= now
        ]
        for state in expired_states:
            self._states.pop(state, None)


class GoogleYouTubeUploadRequestFactory:
    """Build authenticated ``videos.insert`` resumable requests."""

    def __init__(self, oauth_manager: YouTubeOAuthManager):
        self._oauth_manager = oauth_manager

    def is_connected(self) -> bool:
        return self._oauth_manager.status().connected

    def create_request(
        self,
        source_path: Path,
        metadata: YouTubeUploadMetadataDTO,
    ) -> UploadRequestProtocol:
        service = cast(
            _YouTubeServiceProtocol,
            build(
                "youtube",
                "v3",
                credentials=self._oauth_manager.credentials(),
                cache_discovery=False,
            ),
        )
        mime_type = (
            mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        )
        media = MediaFileUpload(
            str(source_path),
            mimetype=mime_type,
            chunksize=UPLOAD_CHUNK_SIZE_BYTES,
            resumable=True,
        )
        body: Mapping[str, object] = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": metadata.made_for_kids,
            },
        }
        return service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=False,
        )


def resolve_upload_source(root: Path, relative_path: str) -> Path:
    """Resolve a stable, completed video under an explicitly allowed directory."""
    if not relative_path or "\\" in relative_path:
        raise ValueError("잘못된 업로드 영상 경로입니다")
    raw_parts = relative_path.split("/")
    if any(part in {"", ".", ".."} or part.startswith(".") for part in raw_parts):
        raise ValueError("업로드할 수 없는 영상 경로입니다")
    pure_path = PurePosixPath(relative_path)
    if (
        pure_path.is_absolute()
        or not pure_path.parts
        or pure_path.parts[0] not in UPLOAD_SOURCE_DIRECTORIES
        or pure_path.suffix.lower() not in UPLOAD_VIDEO_EXTENSIONS
    ):
        raise ValueError("업로드할 수 없는 영상 경로입니다")

    root_resolved = root.resolve()
    try:
        source_path = (root_resolved / Path(*pure_path.parts)).resolve(strict=True)
        source_path.relative_to(root_resolved)
    except (FileNotFoundError, OSError, ValueError):
        raise ValueError(
            "업로드 영상이 존재하지 않거나 허용 범위 밖에 있습니다"
        ) from None
    if not source_path.is_file():
        raise ValueError("업로드 영상이 파일이 아닙니다")
    return source_path


def _is_retryable_upload_error(error: Exception) -> bool:
    if isinstance(error, HttpError):
        return int(error.resp.status) in _RETRIABLE_HTTP_STATUS_CODES
    return isinstance(
        error,
        (ConnectionError, TimeoutError, httplib2.HttpLib2Error),
    )


def _safe_upload_error_message(error: Exception) -> str:
    if isinstance(error, HttpError):
        return f"YouTube API 오류 (HTTP {int(error.resp.status)})"
    message = _UPLOAD_URL_PATTERN.sub("[YouTube upload session]", str(error))
    message = message.replace("\r", " ").replace("\n", " ").strip()
    if not message:
        message = type(error).__name__
    return f"업로드 실패: {message[:160]}"


class YouTubeUploadJobManager:
    """Run resumable uploads in daemon threads and expose in-memory progress."""

    def __init__(
        self,
        root: Path,
        request_factory: YouTubeUploadRequestFactoryProtocol,
        history_limit: int = 50,
        max_retries: int = 5,
        retry_base_seconds: float = 1.0,
    ):
        self._root = root
        self._request_factory = request_factory
        self._history_limit = history_limit
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._jobs: Dict[str, YouTubeUploadJobDTO] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def set_root(self, root: Path) -> None:
        with self._lock:
            self._root = root

    def list_jobs(self) -> List[YouTubeUploadJobDTO]:
        with self._lock:
            return sorted(
                self._jobs.values(), key=lambda job: job.started_at, reverse=True
            )

    def get(self, job_id: str) -> Optional[YouTubeUploadJobDTO]:
        with self._lock:
            return self._jobs.get(job_id)

    def submit(
        self,
        source: str,
        metadata: YouTubeUploadMetadataDTO,
    ) -> YouTubeUploadJobDTO:
        if not self._request_factory.is_connected():
            raise OAuthConnectionError("YouTube 계정을 먼저 연결해 주세요")
        with self._lock:
            root = self._root
        source_path = resolve_upload_source(root, source)
        total_bytes = source_path.stat().st_size
        if total_bytes <= 0:
            raise ValueError("빈 영상 파일은 업로드할 수 없습니다")

        job_id = uuid.uuid4().hex[:12]
        job = YouTubeUploadJobDTO(
            id=job_id,
            source=PurePosixPath(source).as_posix(),
            title=metadata.title,
            status="queued",
            bytes_uploaded=0,
            total_bytes=total_bytes,
            progress_percent=0.0,
            message="업로드 대기 중",
            started_at=time.time(),
            finished_at=None,
            elapsed_seconds=0.0,
            video_id=None,
            video_url=None,
            cancel_requested=False,
        )
        cancel_event = threading.Event()
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_events[job_id] = cancel_event
            self._evict_history_locked()
        threading.Thread(
            target=self._run,
            args=(job_id, source_path, metadata),
            daemon=True,
        ).start()
        return job

    def cancel(self, job_id: str) -> CancelResult:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return "not_found"
            if job.status not in {"queued", "running"}:
                return "not_cancellable"
            job.cancel_requested = True
            cancel_event = self._cancel_events[job_id]
            cancel_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = time.time()
                job.elapsed_seconds = job.finished_at - job.started_at
                job.message = "사용자가 취소함"
            else:
                job.message = "현재 전송 조각 완료 후 취소합니다"
            return "accepted"

    def _run(
        self,
        job_id: str,
        source_path: Path,
        metadata: YouTubeUploadMetadataDTO,
    ) -> None:
        cancel_event = self._cancel_events[job_id]
        try:
            with self._lock:
                job = self._jobs[job_id]
                if job.status == "cancelled":
                    return
                job.status = "running"
                job.message = "YouTube 업로드 준비 중"

            request = self._request_factory.create_request(source_path, metadata)
            retry_count = 0
            response: Optional[Mapping[str, object]] = None
            while response is None:
                if cancel_event.is_set():
                    self._finish_cancelled(job_id)
                    return
                try:
                    progress, response = request.next_chunk(num_retries=0)
                    retry_count = 0
                except Exception as error:
                    if (
                        _is_retryable_upload_error(error)
                        and retry_count < self._max_retries
                    ):
                        retry_count += 1
                        retry_delay = min(
                            32.0,
                            self._retry_base_seconds * (2 ** (retry_count - 1)),
                        ) + random.uniform(0.0, self._retry_base_seconds)
                        with self._lock:
                            current = self._jobs[job_id]
                            current.message = f"일시적 오류로 재시도 중 ({retry_count}/{self._max_retries})"
                            current.elapsed_seconds = time.time() - current.started_at
                        if cancel_event.wait(retry_delay):
                            self._finish_cancelled(job_id)
                            return
                        continue
                    raise

                if response is not None:
                    video_id = response.get("id")
                    if not isinstance(video_id, str) or not video_id:
                        raise RuntimeError("YouTube가 video ID를 반환하지 않았습니다")
                    self._finish_done(job_id, video_id)
                    return

                if progress is not None:
                    with self._lock:
                        current = self._jobs[job_id]
                        uploaded = max(
                            current.bytes_uploaded,
                            min(int(progress.resumable_progress), current.total_bytes),
                        )
                        current.bytes_uploaded = uploaded
                        current.progress_percent = round(
                            uploaded * 100.0 / current.total_bytes, 2
                        )
                        current.message = "YouTube로 전송 중"
                        current.elapsed_seconds = time.time() - current.started_at

                if cancel_event.is_set():
                    self._finish_cancelled(job_id)
                    return
        except Exception as error:
            if cancel_event.is_set():
                self._finish_cancelled(job_id)
            else:
                with self._lock:
                    failed = self._jobs[job_id]
                    failed.status = "failed"
                    failed.message = _safe_upload_error_message(error)
                    failed.finished_at = time.time()
                    failed.elapsed_seconds = failed.finished_at - failed.started_at

    def _finish_done(self, job_id: str, video_id: str) -> None:
        with self._lock:
            completed = self._jobs[job_id]
            completed.status = "done"
            completed.bytes_uploaded = completed.total_bytes
            completed.progress_percent = 100.0
            completed.message = "비공개 업로드 완료"
            completed.video_id = video_id
            completed.video_url = f"https://www.youtube.com/watch?v={video_id}"
            completed.finished_at = time.time()
            completed.elapsed_seconds = completed.finished_at - completed.started_at

    def _finish_cancelled(self, job_id: str) -> None:
        with self._lock:
            cancelled = self._jobs[job_id]
            if cancelled.status == "done":
                return
            cancelled.status = "cancelled"
            cancelled.message = "사용자가 취소함"
            cancelled.finished_at = time.time()
            cancelled.elapsed_seconds = cancelled.finished_at - cancelled.started_at

    def _evict_history_locked(self) -> None:
        if len(self._jobs) <= self._history_limit:
            return
        finished = sorted(
            [
                job
                for job in self._jobs.values()
                if job.status in {"done", "failed", "cancelled"}
            ],
            key=lambda job: job.finished_at or 0.0,
        )
        excess = len(self._jobs) - self._history_limit
        for old_job in finished[:excess]:
            self._jobs.pop(old_job.id, None)
            self._cancel_events.pop(old_job.id, None)
