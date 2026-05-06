"""Pydantic 요청/응답 스키마 — API 라우트가 공유한다."""

from typing import Optional

from pydantic import BaseModel


class ChannelCreateRequest(BaseModel):
    name: str
    url: str
    enabled: bool = True
    download_format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]"


class ChannelUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    download_format: Optional[str] = None


class VideoDownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    audio_only: bool = False


class MonitorStatus(BaseModel):
    is_running: bool
    active_channels: int
    total_channels: int
    state: str = "missing"
    source: str = "yt-monitor"
    last_seen: Optional[float] = None
    age_seconds: Optional[float] = None
    stale: bool = True
    message: str = ""
