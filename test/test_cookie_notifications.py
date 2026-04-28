"""Integration test: web_api 쿠키 엔드포인트가 validator 결과에 따라 알림을 보낸다.

CookieValidator 자체의 단위 테스트는 test_cookie_validator.py.
알림 책임은 validator에서 분리되어 호출자(web_api)로 이동했다.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.cookie_validator import CookieValidator, invalidate_cookie_cache
from src.yt_monitor.web_api import WebAPI


@pytest.fixture(autouse=True)
def reset_default_validator_cache():
    invalidate_cookie_cache()
    yield
    invalidate_cookie_cache()


@pytest.fixture
def channels_file(tmp_path: Path) -> str:
    data = {
        "channels": [],
        "global_settings": {
            "check_interval_seconds": 60,
            "download_directory": str(tmp_path / "downloads"),
            "log_file": str(tmp_path / "test.log"),
            "split_mode": "time",
            "split_time_minutes": 30,
            "split_size_mb": 500,
        },
    }
    path = tmp_path / "channels.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def client_and_notifier(channels_file: str):
    """TestClient + mock notifier + yt-dlp가 인증 실패하는 validator 세팅."""
    mock_notifier = MagicMock()
    fresh_validator = CookieValidator()

    mock_ydl = MagicMock()
    mock_ydl.__enter__ = lambda s: mock_ydl
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.side_effect = Exception(
        "Sign in to confirm you're not a bot"
    )

    with patch("src.yt_monitor.cookie_validator._default_validator", fresh_validator):
        with patch(
            "src.yt_monitor.web_api.routes.cookies.get_notifier",
            return_value=mock_notifier,
        ):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                web_api = WebAPI(channels_file=channels_file)
                yield TestClient(web_api.app), mock_notifier


class TestCookieStatusEndpointNotifications:
    """GET /api/cookie/status — validator 결과에 따른 알림 호출 검증."""

    def test_notifies_when_cookies_invalid(self, client_and_notifier):
        client, mock_notifier = client_and_notifier

        response = client.get("/api/cookie/status")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        mock_notifier.notify_cookie_expired.assert_called_once()
        call_msg = mock_notifier.notify_cookie_expired.call_args.kwargs["message"]
        assert "만료" in call_msg

    def test_does_not_notify_on_cache_hit(self, client_and_notifier):
        """캐시 히트 응답은 알림 재전송하지 않는다."""
        client, mock_notifier = client_and_notifier

        client.get("/api/cookie/status")  # 최초 — 알림 1회
        mock_notifier.notify_cookie_expired.reset_mock()

        client.get("/api/cookie/status")  # 캐시 히트 — 알림 없음

        mock_notifier.notify_cookie_expired.assert_not_called()
