"""YouTube API client module for live stream detection."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import yt_dlp

from .cookie_helper import get_cookie_options
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


class YouTubeClient:
    """Client for interacting with YouTube to detect live streams."""

    def __init__(self):
        self.logger = Logger.get()

    def check_if_live(self, channel_url: str) -> Tuple[bool, Optional[LiveStreamInfo]]:
        # 라이브를 확인하는 3가지 방식
        detection_methods = [
            self._check_live_endpoint,
            self._check_streams_tab,
            self._check_channel_page,
        ]

        auth_errors: List[str] = []
        for method in detection_methods:
            try:
                result = method(channel_url)
                if result:
                    return True, result
            except Exception as e:
                self.logger.debug(f"{method.__name__} failed: {e}")
                if _is_auth_error(e):
                    auth_errors.append(f"{method.__name__}: {e}")

        # 봇 감지가 하나라도 걸리면 라이브 놓칠 수 있음 — 호출자에게 승격
        if auth_errors:
            total_methods = len(detection_methods)
            raise YouTubeAuthError(
                f"YouTube 봇 감지로 {len(auth_errors)}/{total_methods} 탐지 방식 실패:\n"
                + "\n".join(auth_errors)
            )

        return False, None

    @staticmethod
    def _is_entry_live(entry: dict) -> bool:
        """Check if a playlist entry represents a currently live stream.

        yt-dlp uses 'is_live' for full extraction but 'live_status' for
        extract_flat mode. Both must be checked.
        """
        if entry.get("is_live", False):
            return True
        return entry.get("live_status") == "is_live"

    def _check_live_endpoint(self, channel_url: str) -> Optional[LiveStreamInfo]:
        live_url = channel_url.rstrip("/") + "/live"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(live_url, download=False)

            if info and info.get("is_live", False):
                video_id = info.get("id")
                title = info.get("title")
                self.logger.info(f"Live stream found via /live endpoint: {video_id}")

                return LiveStreamInfo(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                )

        return None

    def _check_streams_tab(self, channel_url: str) -> Optional[LiveStreamInfo]:
        streams_url = channel_url.rstrip("/") + "/streams"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(streams_url, download=False)

            if "entries" in info:
                for entry in info["entries"]:
                    if not entry or "id" not in entry:
                        continue

                    if self._is_entry_live(entry):
                        video_id = entry.get("id")
                        title = entry.get("title")
                        self.logger.info(f"Live stream found in /streams: {video_id}")

                        return LiveStreamInfo(
                            video_id=video_id,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            title=title,
                        )

        return None

    def _check_channel_page(self, channel_url: str) -> Optional[LiveStreamInfo]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            if "entries" in info:
                for entry in info["entries"]:
                    if not entry or "id" not in entry:
                        continue

                    if self._is_entry_live(entry):
                        video_id = entry.get("id")
                        title = entry.get("title")
                        self.logger.info(
                            f"Live stream found on channel page: {video_id}"
                        )

                        return LiveStreamInfo(
                            video_id=video_id,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            title=title,
                        )

        return None
