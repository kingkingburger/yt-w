"""Deterministic contracts for YouTube OAuth and resumable uploads."""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

import src.yt_monitor.youtube.upload as upload_module
from src.yt_monitor.youtube.upload import (
    GoogleYouTubeUploadRequestFactory,
    OAuthConnectionError,
    OAuthStateError,
    YouTubeOAuthManager,
    YouTubeOAuthStatusDTO,
    YouTubeUploadJobManager,
    YouTubeUploadMetadataDTO,
    resolve_upload_source,
)


@dataclass(frozen=True)
class _Progress:
    resumable_progress: int


class _ScriptedUploadRequest:
    def __init__(self, actions: list[Any]):
        self._actions = deque(actions)
        self.calls: list[int] = []

    def next_chunk(self, num_retries: int = 0):
        self.calls.append(num_retries)
        if not self._actions:
            raise AssertionError("unexpected next_chunk call")
        action = self._actions.popleft()
        if isinstance(action, BaseException):
            raise action
        if callable(action):
            return action()
        return action


class _FakeRequestFactory:
    def __init__(
        self,
        request: _ScriptedUploadRequest,
        *,
        connected: bool = True,
    ):
        self.request = request
        self.connected = connected
        self.create_calls: list[tuple[Path, YouTubeUploadMetadataDTO]] = []

    def is_connected(self) -> bool:
        return self.connected

    def create_request(
        self,
        source_path: Path,
        metadata: YouTubeUploadMetadataDTO,
    ) -> _ScriptedUploadRequest:
        self.create_calls.append((source_path, metadata))
        return self.request


def _metadata() -> YouTubeUploadMetadataDTO:
    return YouTubeUploadMetadataDTO(
        title="Private upload",
        description="A deterministic test upload",
        tags=["one", "two"],
        category_id="22",
        made_for_kids=False,
    )


def _make_source(
    root: Path,
    relative_path: str = "merged/clip.mp4",
    content: bytes = b"0123456789",
) -> Path:
    source = root.joinpath(*relative_path.split("/"))
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    return source


def _wait_for_status(
    manager: YouTubeUploadJobManager,
    job_id: str,
    expected: str,
    timeout: float = 3.0,
):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job is not None and job.status == expected:
            return job
        time.sleep(0.005)
    job = manager.get(job_id)
    pytest.fail(
        f"job {job_id} did not reach {expected!r}; "
        f"last status was {getattr(job, 'status', None)!r}"
    )


def _write_client_secrets(path: Path, redirect_uri: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "source_directory",
    ["merged", "split", "uploads", "web_downloads"],
)
def test_resolve_upload_source_allows_completed_videos_in_explicit_roots(
    tmp_path: Path,
    source_directory: str,
):
    source = _make_source(
        tmp_path,
        f"{source_directory}/nested/CLIP.MP4",
    )

    resolved = resolve_upload_source(
        tmp_path,
        f"{source_directory}/nested/CLIP.MP4",
    )

    assert resolved == source.resolve()
    assert resolved.is_file()


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "live/clip.mp4",
        "other/clip.mp4",
        "merged/clip.txt",
        "../outside.mp4",
        "merged/../outside.mp4",
        "merged\\clip.mp4",
        "/merged/clip.mp4",
        "merged//clip.mp4",
        "merged/./clip.mp4",
        ".merged/clip.mp4",
        "merged/.hidden/clip.mp4",
        "merged/.clip.mp4",
    ],
)
def test_resolve_upload_source_rejects_unapproved_or_ambiguous_paths(
    tmp_path: Path,
    relative_path: str,
):
    _make_source(tmp_path, "live/clip.mp4")
    (tmp_path / "outside.mp4").write_bytes(b"outside")

    with pytest.raises(ValueError):
        resolve_upload_source(tmp_path, relative_path)


def test_resolve_upload_source_rejects_directory_disguised_as_video(
    tmp_path: Path,
):
    (tmp_path / "merged" / "folder.mp4").mkdir(parents=True)

    with pytest.raises(ValueError):
        resolve_upload_source(tmp_path, "merged/folder.mp4")


def test_resolve_upload_source_rejects_symlink_escape_when_supported(
    tmp_path: Path,
):
    root = tmp_path / "root"
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    link = root / "merged" / "link.mp4"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    with pytest.raises(ValueError):
        resolve_upload_source(root, "merged/link.mp4")


def test_oauth_status_requires_registered_redirect_and_valid_token(
    tmp_path: Path,
):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "oauth" / "token.json"
    redirect_uri = "http://localhost:8088/api/youtube/oauth/callback"
    manager = YouTubeOAuthManager(client_file, token_file, redirect_uri)

    assert manager.status() == YouTubeOAuthStatusDTO(False, False)

    _write_client_secrets(client_file, "http://localhost/wrong-callback")
    assert manager.status() == YouTubeOAuthStatusDTO(False, False)

    _write_client_secrets(client_file, redirect_uri)
    assert manager.status() == YouTubeOAuthStatusDTO(True, False)

    token_file.parent.mkdir(parents=True)
    token_file.write_text('{"refresh_token": "incomplete"}', encoding="utf-8")
    assert manager.status() == YouTubeOAuthStatusDTO(True, False)

    token_file.write_text(
        json.dumps(
            {
                "version": 1,
                "refresh_token": "stored-refresh-token",
                "scopes": [upload_module.YOUTUBE_UPLOAD_SCOPE],
            }
        ),
        encoding="utf-8",
    )
    assert manager.status() == YouTubeOAuthStatusDTO(True, True)


def test_finish_authorization_persists_only_minimal_refresh_token(
    tmp_path: Path,
):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "oauth" / "token.json"
    redirect_uri = "http://localhost:8088/api/youtube/oauth/callback"
    _write_client_secrets(client_file, redirect_uri)
    manager = YouTubeOAuthManager(client_file, token_file, redirect_uri)
    flow = SimpleNamespace(
        fetch_token=MagicMock(),
        credentials=SimpleNamespace(refresh_token="refresh-only"),
    )

    manager.finish_authorization(flow, "authorization-code")

    flow.fetch_token.assert_called_once_with(code="authorization-code")
    persisted = json.loads(token_file.read_text(encoding="utf-8"))
    assert persisted == {
        "version": 1,
        "refresh_token": "refresh-only",
        "scopes": [upload_module.YOUTUBE_UPLOAD_SCOPE],
    }
    assert token_file.read_text(encoding="utf-8").endswith("\n")
    assert manager.status() == YouTubeOAuthStatusDTO(True, True)

    credentials = manager.credentials()
    assert credentials.token is None
    assert credentials.refresh_token == "refresh-only"
    assert credentials.scopes == [upload_module.YOUTUBE_UPLOAD_SCOPE]


def test_oauth_state_is_cookie_bound_single_use_and_burned_on_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client_file = tmp_path / "client.json"
    redirect_uri = "http://localhost:8088/api/youtube/oauth/callback"
    _write_client_secrets(client_file, redirect_uri)
    manager = YouTubeOAuthManager(
        client_file,
        tmp_path / "token.json",
        redirect_uri,
    )
    flow = MagicMock()
    flow.authorization_url.return_value = (
        "https://accounts.example.test/authorize",
        "fixed-state",
    )
    from_client_secrets_file = MagicMock(return_value=flow)
    monkeypatch.setattr(
        upload_module,
        "Flow",
        SimpleNamespace(from_client_secrets_file=from_client_secrets_file),
    )
    monkeypatch.setattr(
        upload_module,
        "secrets",
        SimpleNamespace(
            token_urlsafe=lambda _length: "fixed-state",
            compare_digest=secrets.compare_digest,
        ),
    )

    authorization_url, state = manager.start_authorization()

    assert authorization_url == "https://accounts.example.test/authorize"
    assert state == "fixed-state"
    assert flow.redirect_uri == redirect_uri
    from_client_secrets_file.assert_called_once_with(
        str(client_file),
        scopes=[upload_module.YOUTUBE_UPLOAD_SCOPE],
        state="fixed-state",
    )
    flow.authorization_url.assert_called_once_with(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    with pytest.raises(OAuthStateError):
        manager.consume_state(state, "different-cookie-state")
    with pytest.raises(OAuthStateError):
        manager.consume_state(state, state)

    manager.start_authorization()
    assert manager.consume_state(state, state) is flow
    with pytest.raises(OAuthStateError):
        manager.consume_state(state, state)


def test_google_request_factory_forces_private_resumable_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = _make_source(tmp_path)
    oauth_manager = MagicMock(spec=YouTubeOAuthManager)
    oauth_manager.credentials.return_value = object()
    insert = MagicMock(return_value=object())
    service = SimpleNamespace(
        videos=lambda: SimpleNamespace(insert=insert),
    )
    build = MagicMock(return_value=service)
    media = object()
    media_file_upload = MagicMock(return_value=media)
    monkeypatch.setattr(upload_module, "build", build)
    monkeypatch.setattr(upload_module, "MediaFileUpload", media_file_upload)

    request = GoogleYouTubeUploadRequestFactory(oauth_manager).create_request(
        source,
        _metadata(),
    )

    assert request is insert.return_value
    build.assert_called_once_with(
        "youtube",
        "v3",
        credentials=oauth_manager.credentials.return_value,
        cache_discovery=False,
    )
    media_file_upload.assert_called_once_with(
        str(source),
        mimetype="video/mp4",
        chunksize=upload_module.UPLOAD_CHUNK_SIZE_BYTES,
        resumable=True,
    )
    insert.assert_called_once_with(
        part="snippet,status",
        body={
            "snippet": {
                "title": "Private upload",
                "description": "A deterministic test upload",
                "tags": ["one", "two"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=media,
        notifySubscribers=False,
    )


def test_upload_job_reports_progress_and_completes_with_video_metadata(
    tmp_path: Path,
):
    source = _make_source(tmp_path)
    final_chunk_started = threading.Event()
    release_final_chunk = threading.Event()

    def final_chunk():
        final_chunk_started.set()
        if not release_final_chunk.wait(3.0):
            raise TimeoutError("test did not release final chunk")
        return None, {"id": "video-123"}

    request = _ScriptedUploadRequest(
        [
            (_Progress(6), None),
            (_Progress(3), None),
            final_chunk,
        ]
    )
    factory = _FakeRequestFactory(request)
    manager = YouTubeUploadJobManager(tmp_path, factory)
    metadata = _metadata()

    job = manager.submit("merged/clip.mp4", metadata)
    assert final_chunk_started.wait(2.0)
    try:
        running = manager.get(job.id)
        assert running is not None
        assert running.status == "running"
        assert running.bytes_uploaded == 6
        assert running.total_bytes == 10
        assert running.progress_percent == 60.0
        assert running.video_id is None
        assert factory.create_calls == [(source.resolve(), metadata)]
    finally:
        release_final_chunk.set()

    completed = _wait_for_status(manager, job.id, "done")
    assert request.calls == [0, 0, 0]
    assert completed.bytes_uploaded == 10
    assert completed.progress_percent == 100.0
    assert completed.video_id == "video-123"
    assert completed.video_url == "https://www.youtube.com/watch?v=video-123"
    assert completed.finished_at is not None


def test_queued_cancel_prevents_google_request_creation(tmp_path: Path):
    _make_source(tmp_path)
    request = _ScriptedUploadRequest(
        [AssertionError("cancelled job must not call next_chunk")]
    )
    factory = _FakeRequestFactory(request)
    manager = YouTubeUploadJobManager(tmp_path, factory)
    original_run = manager._run
    worker_entered = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()

    def gated_run(job_id: str, source_path: Path, metadata):
        worker_entered.set()
        release_worker.wait(3.0)
        try:
            original_run(job_id, source_path, metadata)
        finally:
            worker_finished.set()

    manager._run = gated_run  # type: ignore[method-assign]
    job = manager.submit("merged/clip.mp4", _metadata())
    assert worker_entered.wait(2.0)
    try:
        assert manager.cancel(job.id) == "accepted"
        cancelled = manager.get(job.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.cancel_requested is True
        assert cancelled.finished_at is not None
    finally:
        release_worker.set()
        assert worker_finished.wait(2.0)

    assert factory.create_calls == []
    assert request.calls == []


def test_running_cancel_stops_before_requesting_another_chunk(tmp_path: Path):
    _make_source(tmp_path)
    chunk_started = threading.Event()
    release_chunk = threading.Event()

    def in_flight_chunk():
        chunk_started.set()
        if not release_chunk.wait(3.0):
            raise TimeoutError("test did not release in-flight chunk")
        return _Progress(4), None

    request = _ScriptedUploadRequest(
        [
            in_flight_chunk,
            AssertionError("cancelled upload requested another chunk"),
        ]
    )
    manager = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request),
    )
    job = manager.submit("merged/clip.mp4", _metadata())
    assert chunk_started.wait(2.0)
    try:
        assert manager.cancel(job.id) == "accepted"
        cancelling = manager.get(job.id)
        assert cancelling is not None
        assert cancelling.status == "running"
        assert cancelling.cancel_requested is True
    finally:
        release_chunk.set()

    cancelled = _wait_for_status(manager, job.id, "cancelled")
    assert cancelled.bytes_uploaded == 4
    assert request.calls == [0]


def test_final_google_response_wins_race_with_running_cancel(tmp_path: Path):
    _make_source(tmp_path)
    final_chunk_started = threading.Event()
    release_final_chunk = threading.Event()

    def final_chunk():
        final_chunk_started.set()
        if not release_final_chunk.wait(3.0):
            raise TimeoutError("test did not release final response")
        return None, {"id": "already-created"}

    request = _ScriptedUploadRequest([final_chunk])
    manager = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request),
    )
    job = manager.submit("merged/clip.mp4", _metadata())
    assert final_chunk_started.wait(2.0)
    try:
        assert manager.cancel(job.id) == "accepted"
    finally:
        release_final_chunk.set()

    completed = _wait_for_status(manager, job.id, "done")
    assert completed.video_id == "already-created"
    assert completed.cancel_requested is True
    assert manager.cancel(job.id) == "not_cancellable"
    assert request.calls == [0]


def test_retryable_transport_error_is_retried_without_google_retries(
    tmp_path: Path,
):
    _make_source(tmp_path)
    request = _ScriptedUploadRequest(
        [
            ConnectionError("temporary transport failure"),
            (None, {"id": "after-retry"}),
        ]
    )
    manager = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request),
        max_retries=2,
        retry_base_seconds=0.0,
    )

    job = manager.submit("merged/clip.mp4", _metadata())

    completed = _wait_for_status(manager, job.id, "done")
    assert completed.video_id == "after-retry"
    assert request.calls == [0, 0]


def test_http_4xx_fails_without_retry_and_hides_upload_session_url(
    tmp_path: Path,
):
    _make_source(tmp_path)
    response = httplib2.Response({"status": "400"})
    error = HttpError(
        response,
        b'{"error": "invalid metadata"}',
        uri=(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?upload_id=secret-session"
        ),
    )
    request = _ScriptedUploadRequest([error])
    manager = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request),
        max_retries=3,
        retry_base_seconds=0.0,
    )

    job = manager.submit("merged/clip.mp4", _metadata())

    failed = _wait_for_status(manager, job.id, "failed")
    assert request.calls == [0]
    assert "HTTP 400" in failed.message
    assert "secret-session" not in failed.message
    assert failed.video_id is None


def test_submit_rejects_disconnected_account_and_empty_video(tmp_path: Path):
    source = _make_source(tmp_path, content=b"")
    request = _ScriptedUploadRequest([])
    disconnected = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request, connected=False),
    )

    with pytest.raises(OAuthConnectionError):
        disconnected.submit("merged/clip.mp4", _metadata())

    connected = YouTubeUploadJobManager(
        tmp_path,
        _FakeRequestFactory(request),
    )
    with pytest.raises(ValueError):
        connected.submit(source.relative_to(tmp_path).as_posix(), _metadata())
