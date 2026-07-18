"""Operator system-status and Discord test endpoint contracts."""

from collections import namedtuple
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.yt_monitor.channels.repository import ChannelManager
from src.yt_monitor.web.routes import system as system_routes


DiskUsage = namedtuple("DiskUsage", "total used free")


class TestSystemStatusRoute:
    def test_reports_disk_downloads_and_configured_channel_fallback(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        manager.add_channel("Enabled", "https://www.youtube.com/@Enabled")
        manager.add_channel(
            "Disabled",
            "https://www.youtube.com/@Disabled",
            enabled=False,
        )
        root = Path(manager.get_global_settings().download_directory)
        (root / "nested").mkdir(parents=True)
        (root / "one.mp4").write_bytes(b"1234")
        (root / "nested" / "two.mkv").write_bytes(b"123456")
        notifier = MagicMock(is_enabled=False)

        with (
            patch.object(
                system_routes.shutil,
                "disk_usage",
                return_value=DiskUsage(total=1000, used=400, free=600),
            ),
            patch.object(system_routes, "get_notifier", return_value=notifier),
        ):
            response = client.get("/api/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["discord_enabled"] is False
        assert data["downloads"] == {
            "directory": str(root),
            "total_size_bytes": 10,
            "file_count": 2,
        }
        assert data["disk"] == {
            "total_bytes": 1000,
            "used_bytes": 400,
            "free_bytes": 600,
        }
        assert data["monitor"]["active_channels"] == 1
        assert data["monitor"]["total_channels"] == 2
        assert data["monitor"]["is_running"] is False
        assert data["uptime_seconds"] >= 0

    def test_reuses_download_scan_within_cache_ttl(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "one.mp4").write_bytes(b"one")

        with patch.object(
            system_routes,
            "_scan_downloads",
            wraps=system_routes._scan_downloads,
        ) as scan:
            first = client.get("/api/system/status").json()
            (root / "two.mp4").write_bytes(b"two")
            second = client.get("/api/system/status").json()

        assert first["downloads"] == second["downloads"]
        scan.assert_called_once_with(root)


class TestDiscordTestRoute:
    def test_disabled_notifier_returns_reason_without_send(self, client: TestClient):
        notifier = MagicMock(is_enabled=False)
        with patch.object(system_routes, "get_notifier", return_value=notifier):
            response = client.post("/api/system/discord/test")

        assert response.status_code == 200
        assert response.json() == {
            "sent": False,
            "reason": "DISCORD_WEBHOOK_URL not set",
        }
        notifier.send.assert_not_called()

    def test_enabled_notifier_sends_operator_message(self, client: TestClient):
        notifier = MagicMock(is_enabled=True)
        notifier.send.return_value = True
        with patch.object(system_routes, "get_notifier", return_value=notifier):
            response = client.post("/api/system/discord/test")

        assert response.json() == {"sent": True}
        notifier.send.assert_called_once()
        call = notifier.send.call_args.kwargs
        assert call["title"] == "🧪 Webhook Test"
        assert "Operator console" in call["description"]
        assert call["level"] is system_routes.NotificationLevel.INFO
