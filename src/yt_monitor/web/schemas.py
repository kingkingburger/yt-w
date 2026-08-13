"""Pydantic 요청/응답 스키마 — API 라우트가 공유한다."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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


class MergeRequest(BaseModel):
    inputs: List[str]
    output: str
    mode: Literal["concat", "reencode"] = "concat"


class FileDeleteRequest(BaseModel):
    paths: List[str]


class SplitRequest(BaseModel):
    input: str
    strategy: Literal["interval", "parts"]
    interval_seconds: Optional[float] = None
    parts: Optional[int] = None


class SplitUploadResponse(BaseModel):
    path: str
    name: str
    size_bytes: int


class YouTubeUploadRequest(BaseModel):
    source: str = Field(min_length=1, max_length=1024)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: List[str] = Field(default_factory=list, max_length=30)
    category_id: str = "22"
    made_for_kids: bool = False

    @field_validator("source", "title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        if not value:
            raise ValueError("제목을 입력해 주세요")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        if sum(len(tag) for tag in normalized) > 500:
            raise ValueError("태그가 너무 깁니다")
        return normalized

    @field_validator("category_id")
    @classmethod
    def validate_category_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isdigit():
            raise ValueError("category_id는 숫자여야 합니다")
        return normalized


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
