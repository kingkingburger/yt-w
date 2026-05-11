"""YouTube 라이브 감지 클라이언트.

3개 탐지 방식(/streams 탭, 채널 페이지, /live 엔드포인트)이 공통 로직을 공유한다.
URL/옵션/파싱 방식만 다르므로 DetectionStrategy로 캡슐화한다.

/streams와 채널 페이지는 `extract_flat=in_playlist`로 가벼운 playlist
스캔만 수행한다. 다만 YouTube가 라이브 중인 최신 항목에도 live_status를
비워 내려주는 경우가 있어, 마지막 fallback으로 /live 루트 메타데이터를
확인한다.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yt_dlp

from .cookie_options import get_cookie_options
from .logger import Logger


_AUTH_ERROR_PATTERNS: Tuple[str, ...] = (
    "sign in to confirm",
    "not a bot",
    "use --cookies-from-browser",
    "use --cookies",
)


class YouTubeAuthError(Exception):
    """Raised when YouTube bot/cookie authentication blocks live detection.

    Signals that at least one detection method failed with a bot-detection
    or cookie-auth error — recording may be missed without user action.
    """


def _is_auth_error(error: Exception) -> bool:
    """Return True if the exception message matches a YouTube auth failure."""
    message = str(error).lower()
    return any(pattern in message for pattern in _AUTH_ERROR_PATTERNS)


@dataclass
class LiveStreamInfo:
    """Information about a detected live stream."""

    video_id: str
    url: str
    title: Optional[str] = None

    def __post_init__(self):
        if not self.url.startswith("http"):
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class DetectionStrategy:
    """탐지 방식의 URL 변환 + yt-dlp 옵션."""

    name: str
    url_suffix: str  # "" | "/streams"
    extra_opts: Dict[str, Any]


_STREAMS_TAB_STRATEGY = DetectionStrategy(
    name="streams_tab",
    url_suffix="/streams",
    extra_opts={"extract_flat": "in_playlist", "ignoreerrors": True},
)

_CHANNEL_PAGE_STRATEGY = DetectionStrategy(
    name="channel_page",
    url_suffix="",
    extra_opts={"extract_flat": "in_playlist", "ignoreerrors": True},
)

_LIVE_ENDPOINT_STRATEGY = DetectionStrategy(
    name="live_endpoint",
    url_suffix="/live",
    extra_opts={"extract_flat": "in_playlist", "ignoreerrors": True},
)


class YouTubeClient:
    """Client for interacting with YouTube to detect live streams."""

    def __init__(self):
        self.logger = Logger.get()

    def check_if_live(self, channel_url: str) -> Tuple[bool, Optional[LiveStreamInfo]]:
        detection_methods = [
            self._check_streams_tab,
            self._check_channel_page,
            self._check_live_endpoint,
        ]

        auth_errors: List[str] = []
        for method in detection_methods:
            try:
                result = method(channel_url)
                if result:
                    return True, result
            except Exception as error:
                self.logger.debug(f"{method.__name__} failed: {error}")
                if _is_auth_error(error):
                    auth_errors.append(f"{method.__name__}: {error}")

        if auth_errors:
            total_methods = len(detection_methods)
            raise YouTubeAuthError(
                f"YouTube 봇 감지로 {len(auth_errors)}/{total_methods} 탐지 방식 실패:\n"
                + "\n".join(auth_errors)
            )

        return False, None

    @staticmethod
    def _is_entry_live(entry: dict) -> bool:
        """extract_flat 모드는 live_status를, 전체 추출은 is_live를 쓴다 — 둘 다 확인."""
        if entry.get("is_live", False):
            return True
        return entry.get("live_status") == "is_live"

    def _check_streams_tab(self, channel_url: str) -> Optional[LiveStreamInfo]:
        return self._detect_with(channel_url, _STREAMS_TAB_STRATEGY)

    def _check_channel_page(self, channel_url: str) -> Optional[LiveStreamInfo]:
        return self._detect_with(channel_url, _CHANNEL_PAGE_STRATEGY)

    def _check_live_endpoint(self, channel_url: str) -> Optional[LiveStreamInfo]:
        return self._detect_with(channel_url, _LIVE_ENDPOINT_STRATEGY)

    def _detect_with(
        self,
        channel_url: str,
        strategy: DetectionStrategy,
    ) -> Optional[LiveStreamInfo]:
        target_url = channel_url.rstrip("/") + strategy.url_suffix

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            **strategy.extra_opts,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)

        return self._parse_info(info, strategy.name)

    def _parse_info(
        self,
        info: Optional[Dict[str, Any]],
        source_name: str,
    ) -> Optional[LiveStreamInfo]:
        if not info:
            return None

        if info.get("id") and self._is_entry_live(info):
            video_id = info.get("id")
            title = info.get("title")
            self.logger.info(f"Live stream found in {source_name}: {video_id}")
            return LiveStreamInfo(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=title,
            )

        if "entries" not in info:
            return None

        for entry in info["entries"]:
            if not entry or "id" not in entry:
                continue

            if self._is_entry_live(entry):
                video_id = entry.get("id")
                title = entry.get("title")
                self.logger.info(f"Live stream found in {source_name}: {video_id}")
                return LiveStreamInfo(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                )

        return None
