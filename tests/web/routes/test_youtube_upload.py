"""HTTP contracts for YouTube OAuth and private upload routes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.yt_monitor.web.routes.youtube_upload as route_module
from src.yt_monitor.channels.repository import ChannelManager
from src.yt_monitor.media.merge import MergeJobDTO, MergeJobManager
from src.yt_monitor.media.split import SplitJobDTO, SplitJobManager
from src.yt_monitor.web.routes.youtube_upload import (
    OAUTH_STATE_COOKIE_NAME,
    WRITE_REQUEST_HEADER_NAME,
    register_youtube_upload_routes,
)
from src.yt_monitor.youtube.upload import (
    OAuthConfigurationError,
    OAuthConnectionError,
    OAuthStateError,
    YouTubeOAuthManager,
    YouTubeOAuthStatusDTO,
    YouTubeUploadJobDTO,
    YouTubeUploadJobManager,
    YouTubeUploadMetadataDTO,
)


WRITE_HEADERS = {WRITE_REQUEST_HEADER_NAME: "1"}
VALID_UPLOAD = {
    "source": "merged/clip.mp4",
    "title": "Private clip",
    "description": "description",
    "tags": ["one", "two"],
    "category_id": "22",
    "made_for_kids": False,
}


@dataclass
class _RouteHarness:
    client: TestClient
    oauth: MagicMock
    jobs: MagicMock
    merge_jobs: MagicMock
    split_jobs: MagicMock
    channel_manager: MagicMock
    logger: MagicMock
    download_root: Path


def _job(job_id: str = "job-1", status: str = "queued") -> YouTubeUploadJobDTO:
    finished_at: Optional[float] = None
    if status in {"done", "failed", "cancelled"}:
        finished_at = 2.0
    return YouTubeUploadJobDTO(
        id=job_id,
        source="merged/clip.mp4",
        title="Private clip",
        status=status,  # type: ignore[arg-type]
        bytes_uploaded=0,
        total_bytes=10,
        progress_percent=0.0,
        message="queued",
        started_at=1.0,
        finished_at=finished_at,
        elapsed_seconds=0.0,
        video_id=None,
        video_url=None,
        cancel_requested=False,
    )


def _assert_state_cookie_deleted(response) -> None:
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{OAUTH_STATE_COOKIE_NAME.lower()}=")
    assert "max-age=0" in cookie
    assert "path=/api/youtube/oauth/callback" in cookie


@pytest.fixture
def route_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[_RouteHarness]:
    logger = MagicMock()
    monkeypatch.setattr(
        route_module,
        "Logger",
        SimpleNamespace(get=lambda: logger),
    )

    async def immediate_to_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        route_module,
        "asyncio",
        SimpleNamespace(to_thread=immediate_to_thread),
    )

    oauth = MagicMock(spec=YouTubeOAuthManager)
    oauth.redirect_uri = "http://localhost:8088/api/youtube/oauth/callback"
    oauth.state_ttl_seconds = 600.0
    oauth.status.return_value = YouTubeOAuthStatusDTO(True, False)
    jobs = MagicMock(spec=YouTubeUploadJobManager)
    jobs.list_jobs.return_value = []
    merge_jobs = MagicMock(spec=MergeJobManager)
    merge_jobs.list_jobs.return_value = []
    split_jobs = MagicMock(spec=SplitJobManager)
    split_jobs.list_jobs.return_value = []
    channel_manager = MagicMock(spec=ChannelManager)
    channel_manager.get_global_settings.return_value = SimpleNamespace(
        download_directory=str(tmp_path)
    )
    app = FastAPI()
    register_youtube_upload_routes(
        app,
        channel_manager,
        oauth,
        jobs,
        merge_jobs,
        split_jobs,
    )

    with TestClient(app) as client:
        yield _RouteHarness(
            client=client,
            oauth=oauth,
            jobs=jobs,
            merge_jobs=merge_jobs,
            split_jobs=split_jobs,
            channel_manager=channel_manager,
            logger=logger,
            download_root=tmp_path,
        )


def test_oauth_status_exposes_configuration_and_connection(
    route_harness: _RouteHarness,
):
    route_harness.oauth.status.return_value = YouTubeOAuthStatusDTO(True, True)

    response = route_harness.client.get("/api/youtube/oauth/status")

    assert response.status_code == 200
    assert response.json() == {"configured": True, "connected": True}
    route_harness.oauth.status.assert_called_once_with()


@pytest.mark.parametrize("request_marker", [None, "0"])
@pytest.mark.parametrize(
    ("method", "url", "payload"),
    [
        ("POST", "/api/youtube/oauth/start", None),
        ("DELETE", "/api/youtube/oauth/connection", None),
        ("POST", "/api/youtube/uploads", VALID_UPLOAD),
        ("POST", "/api/youtube/uploads/job-1/cancel", None),
    ],
)
def test_mutating_routes_require_custom_request_header(
    route_harness: _RouteHarness,
    request_marker: Optional[str],
    method: str,
    url: str,
    payload,
):
    headers = {}
    if request_marker is not None:
        headers[WRITE_REQUEST_HEADER_NAME] = request_marker
    kwargs = {"headers": headers}
    if payload is not None:
        kwargs["json"] = payload

    response = route_harness.client.request(method, url, **kwargs)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("redirect_uri", "expects_secure"),
    [
        ("http://localhost:8088/api/youtube/oauth/callback", False),
        ("https://upload.example.test/api/youtube/oauth/callback", True),
    ],
)
def test_oauth_start_sets_short_lived_callback_scoped_state_cookie(
    route_harness: _RouteHarness,
    redirect_uri: str,
    expects_secure: bool,
):
    route_harness.oauth.redirect_uri = redirect_uri
    route_harness.oauth.state_ttl_seconds = 321.9
    route_harness.oauth.start_authorization.return_value = (
        "https://accounts.example.test/authorize",
        "state-value",
    )

    response = route_harness.client.post(
        "/api/youtube/oauth/start",
        headers=WRITE_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "authorization_url": "https://accounts.example.test/authorize"
    }
    assert response.cookies[OAUTH_STATE_COOKIE_NAME] == "state-value"
    cookie = response.headers["set-cookie"].lower()
    assert "max-age=321" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/youtube/oauth/callback" in cookie
    assert ("; secure" in cookie) is expects_secure


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (OAuthConfigurationError("not configured"), 503),
        (OAuthConnectionError("provider unavailable"), 502),
    ],
)
def test_oauth_start_maps_configuration_and_provider_errors(
    route_harness: _RouteHarness,
    error: Exception,
    expected_status: int,
):
    route_harness.oauth.start_authorization.side_effect = error

    response = route_harness.client.post(
        "/api/youtube/oauth/start",
        headers=WRITE_HEADERS,
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_oauth_callback_rejects_invalid_state_and_clears_cookie(
    route_harness: _RouteHarness,
):
    route_harness.oauth.consume_state.side_effect = OAuthStateError("mismatch")
    route_harness.client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        "cookie-state",
        path="/api/youtube/oauth/callback",
    )

    response = route_harness.client.get(
        "/api/youtube/oauth/callback?state=query-state&code=code",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/?youtube_oauth=invalid_state#youtube-upload"
    )
    _assert_state_cookie_deleted(response)
    route_harness.oauth.consume_state.assert_called_once_with(
        "query-state",
        "cookie-state",
    )
    route_harness.oauth.finish_authorization.assert_not_called()


def test_oauth_callback_exchanges_code_and_redirects_connected(
    route_harness: _RouteHarness,
):
    flow = object()
    route_harness.oauth.consume_state.return_value = flow
    route_harness.client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        "same-state",
        path="/api/youtube/oauth/callback",
    )

    response = route_harness.client.get(
        "/api/youtube/oauth/callback?state=same-state&code=code-123",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/?youtube_oauth=connected#youtube-upload"
    )
    _assert_state_cookie_deleted(response)
    route_harness.oauth.consume_state.assert_called_once_with(
        "same-state",
        "same-state",
    )
    route_harness.oauth.finish_authorization.assert_called_once_with(
        flow,
        "code-123",
    )


@pytest.mark.parametrize(
    ("provider_error", "expected_result"),
    [
        ("access_denied", "denied"),
        ("temporarily_unavailable", "error"),
    ],
)
def test_oauth_callback_maps_provider_error_without_token_exchange(
    route_harness: _RouteHarness,
    provider_error: str,
    expected_result: str,
):
    route_harness.oauth.consume_state.return_value = object()
    route_harness.client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        "same-state",
        path="/api/youtube/oauth/callback",
    )

    response = route_harness.client.get(
        "/api/youtube/oauth/callback",
        params={"state": "same-state", "error": provider_error},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/?youtube_oauth={expected_result}#youtube-upload"
    )
    _assert_state_cookie_deleted(response)
    route_harness.oauth.finish_authorization.assert_not_called()


def test_oauth_callback_maps_token_exchange_failure_to_safe_redirect(
    route_harness: _RouteHarness,
):
    route_harness.oauth.consume_state.return_value = object()
    route_harness.oauth.finish_authorization.side_effect = OAuthConnectionError(
        "sensitive provider detail"
    )
    route_harness.client.cookies.set(
        OAUTH_STATE_COOKIE_NAME,
        "same-state",
        path="/api/youtube/oauth/callback",
    )

    response = route_harness.client.get(
        "/api/youtube/oauth/callback?state=same-state&code=bad-code",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/?youtube_oauth=error#youtube-upload"
    )
    assert "sensitive" not in response.headers["location"]
    _assert_state_cookie_deleted(response)


def test_disconnect_invokes_manager_off_event_loop(
    route_harness: _RouteHarness,
):
    response = route_harness.client.delete(
        "/api/youtube/oauth/connection",
        headers=WRITE_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"connected": False}
    route_harness.oauth.disconnect.assert_called_once_with()


def test_submit_normalizes_metadata_sets_current_root_and_returns_202(
    route_harness: _RouteHarness,
):
    job = _job()
    route_harness.jobs.submit.return_value = job

    response = route_harness.client.post(
        "/api/youtube/uploads",
        headers=WRITE_HEADERS,
        json={
            "source": "  merged/clip.mp4  ",
            "title": "  Private clip  ",
            "description": "  description  ",
            "tags": [" one ", "", "two", "one"],
            "category_id": " 22 ",
            "made_for_kids": True,
        },
    )

    assert response.status_code == 202
    assert response.json() == asdict(job)
    route_harness.jobs.set_root.assert_called_once_with(
        route_harness.download_root
    )
    route_harness.jobs.submit.assert_called_once_with(
        source="merged/clip.mp4",
        metadata=YouTubeUploadMetadataDTO(
            title="Private clip",
            description="description",
            tags=["one", "two"],
            category_id="22",
            made_for_kids=True,
        ),
    )


@pytest.mark.parametrize("source_kind", ["merge", "split"])
def test_submit_rejects_active_merge_or_split_output(
    route_harness: _RouteHarness,
    source_kind: str,
):
    payload = dict(VALID_UPLOAD)
    if source_kind == "merge":
        route_harness.merge_jobs.list_jobs.return_value = [
            MergeJobDTO(
                id="merge-1",
                inputs=["one.mp4", "two.mp4"],
                output="merged/clip.mp4",
                mode="concat",
                status="running",
                started_at=1.0,
                finished_at=None,
                message="병합 중",
                elapsed_seconds=1.0,
            )
        ]
    else:
        payload["source"] = "split/clip.mp4"
        route_harness.split_jobs.list_jobs.return_value = [
            SplitJobDTO(
                id="split-1",
                input="uploads/source.mp4",
                outputs=["split/clip.mp4"],
                strategy="parts",
                interval_seconds=None,
                parts=2,
                duration_seconds=60.0,
                total_parts=2,
                completed_parts=0,
                status="queued",
                started_at=1.0,
                finished_at=None,
                message="대기 중",
                elapsed_seconds=0.0,
            )
        ]

    response = route_harness.client.post(
        "/api/youtube/uploads",
        headers=WRITE_HEADERS,
        json=payload,
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "병합 또는 분할이 끝난 뒤 업로드해 주세요"
    }
    route_harness.jobs.submit.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (OAuthConnectionError("connect first"), 401),
        (ValueError("source path is not allowed"), 400),
    ],
)
def test_submit_maps_auth_and_path_errors(
    route_harness: _RouteHarness,
    error: Exception,
    expected_status: int,
):
    route_harness.jobs.submit.side_effect = error

    response = route_harness.client.post(
        "/api/youtube/uploads",
        headers=WRITE_HEADERS,
        json=VALID_UPLOAD,
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_list_get_and_cancel_result_mapping(route_harness: _RouteHarness):
    job = _job()
    route_harness.jobs.list_jobs.return_value = [job]
    route_harness.jobs.get.side_effect = lambda job_id: (
        job if job_id == job.id else None
    )
    route_harness.jobs.cancel.side_effect = lambda job_id: {
        "missing": "not_found",
        "done": "not_cancellable",
        "job-1": "accepted",
    }[job_id]

    listed = route_harness.client.get("/api/youtube/uploads")
    fetched = route_harness.client.get(f"/api/youtube/uploads/{job.id}")
    missing = route_harness.client.get("/api/youtube/uploads/missing")
    cancel_missing = route_harness.client.post(
        "/api/youtube/uploads/missing/cancel",
        headers=WRITE_HEADERS,
    )
    cancel_done = route_harness.client.post(
        "/api/youtube/uploads/done/cancel",
        headers=WRITE_HEADERS,
    )
    cancel_accepted = route_harness.client.post(
        f"/api/youtube/uploads/{job.id}/cancel",
        headers=WRITE_HEADERS,
    )

    assert listed.status_code == 200
    assert listed.json() == [asdict(job)]
    assert fetched.status_code == 200
    assert fetched.json() == asdict(job)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Job not found"}
    assert cancel_missing.status_code == 404
    assert cancel_missing.json() == {"detail": "Job not found"}
    assert cancel_done.status_code == 409
    assert cancel_done.json() == {"detail": "Cannot cancel job"}
    assert cancel_accepted.status_code == 200
    assert cancel_accepted.json() == {"cancel_requested": True}
