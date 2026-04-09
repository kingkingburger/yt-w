"""Tests for discord_notifier module."""

import json
from unittest.mock import MagicMock

import pytest

from src.yt_monitor.discord_notifier import DiscordNotifier, NotificationLevel, get_notifier


class TestNotificationLevel:
    """Test NotificationLevel enum."""

    def test_all_levels_have_color_values(self):
        assert NotificationLevel.INFO.value == 0x3498DB
        assert NotificationLevel.SUCCESS.value == 0x2ECC71
        assert NotificationLevel.WARNING.value == 0xF39C12
        assert NotificationLevel.ERROR.value == 0xE74C3C


class TestDiscordNotifier:
    """Test cases for DiscordNotifier class."""

    def test_disabled_when_no_webhook_url(self):
        """webhook URL 없으면 비활성화되고 모든 send가 False."""
        notifier = DiscordNotifier(webhook_url="")
        assert not notifier.is_enabled
        assert not notifier.send("title", "desc")

    def test_enabled_when_webhook_url_set(self):
        """webhook URL 있으면 활성화."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        assert notifier.is_enabled

    def test_uses_env_variable_when_no_url_passed(self, monkeypatch):
        """DISCORD_WEBHOOK_URL 환경변수에서 URL 읽기."""
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/env/token")
        notifier = DiscordNotifier()
        assert notifier.is_enabled

    def test_send_success(self, discord_mock_urlopen):
        """정상 전송 — HTTP 200 응답."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        result = notifier.send("Test Title", "Test description", NotificationLevel.INFO)

        assert result is True
        discord_mock_urlopen.assert_called_once()

    def test_send_builds_correct_payload(self, discord_mock_urlopen):
        """전송 payload가 Discord embed 형식을 따르는지."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token", service_name="yt-test")
        notifier.send("My Title", "My Description", NotificationLevel.ERROR)

        request = discord_mock_urlopen.call_args[0][0]
        payload = json.loads(request.data)

        assert "embeds" in payload
        embed = payload["embeds"][0]
        assert embed["title"] == "My Title"
        assert embed["description"] == "My Description"
        assert embed["color"] == NotificationLevel.ERROR.value
        assert embed["footer"]["text"] == "yt-test"

    def test_send_returns_false_on_http_error(self, discord_mock_urlopen):
        """HTTP 에러 시 False 반환."""
        import urllib.error
        discord_mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=500, msg="Internal Server Error", hdrs=MagicMock(), fp=None
        )

        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        result = notifier.send("title", "desc")

        assert result is False

    def test_send_returns_false_on_url_error(self, discord_mock_urlopen):
        """네트워크 에러 시 False 반환."""
        import urllib.error
        discord_mock_urlopen.side_effect = urllib.error.URLError(reason="connection refused")

        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        result = notifier.send("title", "desc")

        assert result is False

    def test_send_disabled_returns_false_without_network(self):
        """비활성화 시 네트워크 호출 없이 즉시 False."""
        notifier = DiscordNotifier(webhook_url="")
        assert not notifier.send("title", "desc", NotificationLevel.ERROR)

    def test_convenience_methods_disabled(self):
        """비활성화 상태에서 편의 메서드 모두 False."""
        notifier = DiscordNotifier(webhook_url="")
        assert not notifier.notify_live_detected("채널", "url", "title")
        assert not notifier.notify_download_complete("채널", "title")
        assert not notifier.notify_download_failed("채널", "에러")
        assert not notifier.notify_cookie_expired("메시지")
        assert not notifier.notify_monitor_started(3)
        assert not notifier.notify_monitor_stopped("test")
        assert not notifier.notify_error("채널", "에러")

    def test_notify_live_detected_title_format(self, discord_mock_urlopen):
        """라이브 감지 알림 제목 형식 검증."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        notifier.notify_live_detected("침착맨", "https://youtube.com/watch?v=xxx", "라이브 방송")

        request = discord_mock_urlopen.call_args[0][0]
        payload = json.loads(request.data)
        embed = payload["embeds"][0]

        assert "침착맨" in embed["title"]
        assert embed["color"] == NotificationLevel.INFO.value

    def test_notify_download_complete_title_format(self, discord_mock_urlopen):
        """다운로드 완료 알림 제목 형식 검증."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        notifier.notify_download_complete("채널명", "방송 제목")

        request = discord_mock_urlopen.call_args[0][0]
        payload = json.loads(request.data)
        embed = payload["embeds"][0]

        assert embed["color"] == NotificationLevel.SUCCESS.value

    def test_send_with_fields(self, discord_mock_urlopen):
        """fields 파라미터가 embed에 포함되는지 검증."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/token")
        fields = [{"name": "채널", "value": "테스트", "inline": "true"}]
        notifier.send("title", "desc", fields=fields)

        request = discord_mock_urlopen.call_args[0][0]
        payload = json.loads(request.data)
        assert payload["embeds"][0]["fields"] == fields


class TestGetNotifier:
    """Test get_notifier singleton."""

    def test_get_notifier_returns_discord_notifier(self):
        """get_notifier()가 DiscordNotifier 인스턴스를 반환하는지."""
        notifier = get_notifier()
        assert isinstance(notifier, DiscordNotifier)

    def test_get_notifier_returns_same_instance(self):
        """get_notifier()가 매번 같은 인스턴스를 반환하는지."""
        assert get_notifier() is get_notifier()
