"""/api/channels 엔드포인트."""

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException

from ...channel_manager import ChannelManager
from ...util.sanitize_url import sanitize_youtube_url
from ..dto_converters import channel_to_dict
from ..schemas import ChannelCreateRequest, ChannelUpdateRequest
from ..state import MonitorState


def register_channel_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    monitor_state: MonitorState,
) -> None:
    @app.get("/api/channels", response_model=List[Dict[str, Any]])
    async def list_channels(enabled_only: bool = False):
        channels = channel_manager.list_channels(enabled_only=enabled_only)
        return [channel_to_dict(ch) for ch in channels]

    @app.post("/api/channels", response_model=Dict[str, Any])
    async def create_channel(channel: ChannelCreateRequest):
        try:
            clean_url = sanitize_youtube_url(channel.url)
            new_channel = channel_manager.add_channel(
                name=channel.name,
                url=clean_url,
                enabled=channel.enabled,
                download_format=channel.download_format,
            )

            if monitor_state.is_running and new_channel.enabled:
                monitor_state.monitor.add_channel_and_start_monitoring(new_channel)

            return channel_to_dict(new_channel)

        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.patch("/api/channels/{channel_id}", response_model=Dict[str, Any])
    async def update_channel(channel_id: str, channel: ChannelUpdateRequest):
        clean_url = sanitize_youtube_url(channel.url) if channel.url else None

        updated_channel = channel_manager.update_channel(
            channel_id=channel_id,
            name=channel.name,
            url=clean_url,
            enabled=channel.enabled,
            download_format=channel.download_format,
        )

        if not updated_channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        if monitor_state.is_running and channel.enabled is not None:
            if channel.enabled:
                monitor_state.monitor.add_channel_and_start_monitoring(updated_channel)
            else:
                monitor_state.monitor.remove_channel_and_stop_monitoring(channel_id)

        return channel_to_dict(updated_channel)

    @app.delete("/api/channels/{channel_id}")
    async def delete_channel(channel_id: str):
        if monitor_state.is_running:
            monitor_state.monitor.remove_channel_and_stop_monitoring(channel_id)

        success = channel_manager.remove_channel(channel_id)

        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")

        return {"message": "Channel deleted successfully"}
