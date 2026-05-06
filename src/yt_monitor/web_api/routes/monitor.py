"""/api/monitor/* endpoints.

yt-web is a status surface only. The actual recorder daemon runs in the
separate yt-monitor container and publishes a heartbeat into the shared logs
volume.
"""

from fastapi import FastAPI, HTTPException

from ...channel_manager import ChannelManager
from ...monitor_status import read_monitor_status
from ..schemas import MonitorStatus


def register_monitor_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
) -> None:
    @app.get("/api/monitor/status", response_model=MonitorStatus)
    async def get_monitor_status():
        total_channels = len(channel_manager.list_channels())
        active_channels = len(channel_manager.list_channels(enabled_only=True))
        settings = channel_manager.get_global_settings()
        daemon_status = read_monitor_status(settings.log_file)

        return MonitorStatus(
            is_running=daemon_status["is_running"],
            active_channels=daemon_status["active_channels"]
            if daemon_status["active_channels"] is not None
            else active_channels,
            total_channels=daemon_status["total_channels"]
            if daemon_status["total_channels"] is not None
            else total_channels,
            state=daemon_status["state"],
            source=daemon_status["source"],
            last_seen=daemon_status["last_seen"],
            age_seconds=daemon_status["age_seconds"],
            stale=daemon_status["stale"],
            message=daemon_status["message"],
        )

    @app.post("/api/monitor/start")
    async def start_monitor():
        raise HTTPException(
            status_code=405,
            detail="Monitor is managed by the yt-monitor container",
        )

    @app.post("/api/monitor/stop")
    async def stop_monitor():
        raise HTTPException(
            status_code=405,
            detail="Monitor is managed by the yt-monitor container",
        )
