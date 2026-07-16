"""라이브 녹화 분할 전략 — StreamDownloader가 이 중 하나를 쓴다.

책임: split_mode 문자열 해석 + split_seconds 계산.
ffmpeg 명령 조립은 ffmpeg_command.py, I/O 실행은 StreamDownloader가 담당.
"""

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class SplitStrategy(Protocol):
    """분할 전략 프로토콜 — split_seconds는 None(분할 안 함) 또는 양의 int."""

    def split_seconds(self) -> Optional[int]: ...


@dataclass(frozen=True)
class NoSplit:
    """분할하지 않고 단일 파일로 저장."""

    def split_seconds(self) -> Optional[int]:
        return None


@dataclass(frozen=True)
class TimeSplit:
    """고정 시간 간격으로 분할."""

    minutes: int

    def __post_init__(self):
        if self.minutes <= 0:
            raise ValueError("TimeSplit.minutes must be positive")

    def split_seconds(self) -> int:
        return self.minutes * 60


@dataclass(frozen=True)
class SizeSplit:
    """예상 비트레이트를 써서 목표 파일 크기에 도달할 시간으로 분할."""

    megabytes: int
    estimated_bitrate_mbps: int = 5

    def __post_init__(self):
        if self.megabytes <= 0:
            raise ValueError("SizeSplit.megabytes must be positive")
        if self.estimated_bitrate_mbps <= 0:
            raise ValueError("SizeSplit.estimated_bitrate_mbps must be positive")

    def split_seconds(self) -> int:
        return int((self.megabytes * 8) / self.estimated_bitrate_mbps)


def make_split_strategy(
    mode: str,
    time_minutes: int,
    size_mb: int,
) -> SplitStrategy:
    """split_mode 문자열을 Strategy 인스턴스로 변환한다."""
    if mode == "none":
        return NoSplit()
    if mode == "time":
        return TimeSplit(minutes=time_minutes)
    if mode == "size":
        return SizeSplit(megabytes=size_mb)
    raise ValueError(f"Invalid split_mode: {mode}")
