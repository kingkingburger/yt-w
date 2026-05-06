"""/api/system/* — operator console에 필요한 통합 헬스/상태."""

import asyncio
import shutil
import time
from pathlib import Path

from fastapi import FastAPI

from ...channel_manager import ChannelManager
from ...discord_notifier import NotificationLevel, get_notifier
from ...monitor_status import read_monitor_status

DOWNLOADS_CACHE_TTL_SECONDS = 30.0


def _scan_downloads(download_root: Path) -> tuple[int, int]:
    downloads_size = 0
    downloads_count = 0
    if not download_root.exists():
        return downloads_size, downloads_count

    try:
        entries = download_root.rglob("*")
        for entry in entries:
            try:
                if entry.is_file():
                    downloads_size += entry.stat().st_size
                    downloads_count += 1
            except OSError:
                continue
    except OSError:
        pass
    return downloads_size, downloads_count


def register_system_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    boot_time: float,
) -> None:
    downloads_cache = {
        "root": "",
        "expires_at": 0.0,
        "size": 0,
        "count": 0,
    }

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

        now = time.time()
        root_key = str(download_root.resolve())
        if (
            downloads_cache["root"] == root_key
            and float(downloads_cache["expires_at"]) > now
        ):
            downloads_size = int(downloads_cache["size"])
            downloads_count = int(downloads_cache["count"])
        else:
            downloads_size, downloads_count = await asyncio.to_thread(
                _scan_downloads, download_root
            )
            downloads_cache.update(
                {
                    "root": root_key,
                    "expires_at": now + DOWNLOADS_CACHE_TTL_SECONDS,
                    "size": downloads_size,
                    "count": downloads_count,
                }
            )

        notifier = get_notifier()
        configured_active_channels = len(
            channel_manager.list_channels(enabled_only=True)
        )
        configured_total_channels = len(channel_manager.list_channels())
        monitor = read_monitor_status(settings.log_file)
        monitor.update(
            {
                "active_channels": monitor["active_channels"]
                if monitor["active_channels"] is not None
                else configured_active_channels,
                "total_channels": monitor["total_channels"]
                if monitor["total_channels"] is not None
                else configured_total_channels,
            }
        )
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
            "monitor": monitor,
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
