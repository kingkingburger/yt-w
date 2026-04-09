"""Tests for cookie_helper module — 쿠키 만료 알림 검증 포함."""

from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.cookie_helper import (
    invalidate_cookie_cache,
    validate_cookies,
)


@pytest.fixture(autouse=True)
def reset_cookie_cache():
    """각 테스트 전/후에 캐시를 초기화한다."""
    invalidate_cookie_cache()
    yield
    invalidate_cookie_cache()


class TestValidateCookiesNotifications:
    """쿠키 만료 시 Discord 알림이 전송되는지 검증."""

    def test_notifies_when_cookies_file_missing(self, tmp_path):
        """cookies.txt 파일이 없으면 notify_cookie_expired가 호출된다."""
        mock_notifier = MagicMock()
        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(tmp_path / "no_cookies.txt")):
            with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                result = validate_cookies()

        assert result["valid"] is False
        assert result["has_cookies"] is False
        mock_notifier.notify_cookie_expired.assert_called_once_with(
            message="cookies.txt 파일이 없습니다"
        )

    def test_notifies_when_yt_dlp_extraction_fails(self, tmp_path):
        """yt-dlp 추출 예외 시 notify_cookie_expired가 호출된다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_notifier = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("Sign in to confirm your age")

        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(cookies_file)):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                    result = validate_cookies()

        assert result["valid"] is False
        mock_notifier.notify_cookie_expired.assert_called_once()
        assert "만료" in mock_notifier.notify_cookie_expired.call_args.kwargs["message"]

    def test_notifies_when_yt_dlp_returns_no_title(self, tmp_path):
        """yt-dlp가 title 없는 info를 반환하면 notify_cookie_expired가 호출된다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_notifier = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "jNQXAC9IVRw"}  # title 없음

        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(cookies_file)):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                    result = validate_cookies()

        assert result["valid"] is False
        mock_notifier.notify_cookie_expired.assert_called_once_with(
            message="쿠키 만료됨 — 브라우저에서 다시 내보내세요"
        )

    def test_does_not_notify_when_cookies_valid(self, tmp_path):
        """쿠키가 유효하면 notify_cookie_expired가 호출되지 않는다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_notifier = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "jNQXAC9IVRw", "title": "Me at the zoo"}

        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(cookies_file)):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                    result = validate_cookies()

        assert result["valid"] is True
        mock_notifier.notify_cookie_expired.assert_not_called()

    def test_does_not_notify_on_cache_hit(self, tmp_path):
        """캐시된 결과 반환 시 notify_cookie_expired가 호출되지 않는다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_notifier = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "jNQXAC9IVRw", "title": "Me at the zoo"}

        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(cookies_file)):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                    # 첫 번째 호출 — 실제 검사
                    validate_cookies()
                    # 두 번째 호출 — 캐시 히트
                    result = validate_cookies()

        assert result["cached"] is True
        # yt-dlp는 한 번만 호출됨 (캐시 히트)
        assert mock_ydl.extract_info.call_count == 1
        mock_notifier.notify_cookie_expired.assert_not_called()

    def test_force_bypasses_cache_and_notifies(self, tmp_path):
        """force=True이면 캐시를 무시하고 재검사 후 알림을 전송한다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_notifier = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("cookies expired")

        with patch("src.yt_monitor.cookie_helper._COOKIE_SOURCE_PATH", str(cookies_file)):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch("src.yt_monitor.cookie_helper.get_notifier", return_value=mock_notifier):
                    result = validate_cookies(force=True)

        assert result["valid"] is False
        assert result["cached"] is False
        mock_notifier.notify_cookie_expired.assert_called_once()
