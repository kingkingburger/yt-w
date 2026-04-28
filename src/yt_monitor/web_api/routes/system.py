"""/api/system/* — operator console에 필요한 통합 헬스/상태."""

import shutil
import time
from pathlib import Path

from fastapi import FastAPI

from ...channel_manager import ChannelManager
from ...discord_notifier import NotificationLevel, get_notifier
from ..state import MonitorState


def register_system_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    monitor_state: MonitorState,
    boot_time: float,
) -> None:
    @app.get("/api/system/status")
    async def system_status():
        settings = channel_manager.get_global_settings()
        download_root = Path(settings.download_directory)

        try:
            target = download_root if download_root.exists() else Path(".")
            disk = shutil.disk_usage(target)
            disk_total = disk.total
            disk_used = disk.used
            disk_free = disk.free
        except OSError:
            disk_total = disk_used = disk_free = 0

        downloads_size = 0
        downloads_count = 0
        try:
            for entry in download_root.rglob("*"):
                if entry.is_file():
                    downloads_size += entry.stat().st_size
                    downloads_count += 1
        except OSError:
            pass

        notifier = get_notifier()
        return {
            "boot_time": boot_time,
            "uptime_seconds": time.time() - boot_time,
            "discord_enabled": notifier.is_enabled,
            "downloads": {
                "directory": str(download_root),
                "total_size_bytes": downloads_size,
                "file_count": downloads_count,
            },
            "disk": {
                "total_bytes": disk_total,
                "used_bytes": disk_used,
                "free_bytes": disk_free,
            },
            "monitor": {
                "is_running": monitor_state.is_running,
                "active_channels": len(
                    channel_manager.list_channels(enabled_only=True)
                ),
                "total_channels": len(channel_manager.list_channels()),
            },
        }

    @app.post("/api/system/discord/test")
    async def discord_test():
        notifier = get_notifier()
        if not notifier.is_enabled:
            return {"sent": False, "reason": "DISCORD_WEBHOOK_URL not set"}
        ok = notifier.send(
            title="🧪 Webhook Test",
            description="Operator console에서 발송한 테스트 메시지입니다.",
            level=NotificationLevel.INFO,
        )
        return {"sent": ok}
