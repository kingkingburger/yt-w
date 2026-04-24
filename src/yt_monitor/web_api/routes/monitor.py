"""/api/monitor/* 엔드포인트."""

import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException

from ...channel_manager import ChannelManager
from ...logger import Logger
from ...multi_channel_monitor import MultiChannelMonitor
from ..schemas import MonitorStatus
from ..state import MonitorState


def register_monitor_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    monitor_state: MonitorState,
) -> None:
    logger = Logger.get()

    @app.get("/api/monitor/status", response_model=MonitorStatus)
    async def get_monitor_status():
        total_channels = len(channel_manager.list_channels())
        active_channels = len(channel_manager.list_channels(enabled_only=True))

        return MonitorStatus(
            is_running=monitor_state.is_running,
            active_channels=active_channels,
            total_channels=total_channels,
        )

    @app.post("/api/monitor/start")
    async def start_monitor(background_tasks: BackgroundTasks):
        if monitor_state.is_running:
            raise HTTPException(status_code=400, detail="Monitor is already running")

        channels = channel_manager.list_channels(enabled_only=True)
        if not channels:
            raise HTTPException(
                status_code=400, detail="No enabled channels to monitor"
            )

        monitor_state.monitor = MultiChannelMonitor(channel_manager=channel_manager)

        def run_monitor():
            try:
                monitor_state.monitor.start()
            except Exception as error:
                logger.error(f"Monitor error: {error}")

        monitor_state.monitor_thread = threading.Thread(
            target=run_monitor, daemon=True
        )
        monitor_state.monitor_thread.start()

        return {"message": "Monitor started successfully"}

    @app.post("/api/monitor/stop")
    async def stop_monitor():
        if not monitor_state.is_running:
            raise HTTPException(status_code=400, detail="Monitor is not running")

        monitor_state.monitor.stop()

        if monitor_state.monitor_thread is not None:
            monitor_state.monitor_thread.join(timeout=5.0)

        return {"message": "Monitor stopped successfully"}
