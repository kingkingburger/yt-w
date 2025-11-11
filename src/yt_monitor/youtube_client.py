"""YouTube API client module for live stream detection."""

from dataclasses import dataclass
from typing import Optional, Tuple

import yt_dlp

from .logger import Logger


@dataclass
class LiveStreamInfo:
    """Information about a detected live stream."""

    video_id: str
    url: str
    title: Optional[str] = None

    def __post_init__(self):
        if not self.url.startswith('http'):
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"


class YouTubeClient:
    """Client for interacting with YouTube to detect live streams."""

    def __init__(self):
        self.logger = Logger.get()

    def check_if_live(self, channel_url: str) -> Tuple[bool, Optional[LiveStreamInfo]]:
        detection_methods = [
            self._check_live_endpoint,
            self._check_streams_tab,
            self._check_channel_page,
        ]

        for method in detection_methods:
            try:
                result = method(channel_url)
                if result:
                    return True, result
            except Exception as e:
                self.logger.debug(f"{method.__name__} failed: {e}")

        return False, None

    def _check_live_endpoint(self, channel_url: str) -> Optional[LiveStreamInfo]:
        live_url = channel_url.rstrip('/') + '/live'

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(live_url, download=False)

            if info and info.get('is_live', False):
                video_id = info.get('id')
                title = info.get('title')
                self.logger.info(f"Live stream found via /live endpoint: {video_id}")

                return LiveStreamInfo(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title
                )

        return None

    def _check_streams_tab(self, channel_url: str) -> Optional[LiveStreamInfo]:
        streams_url = channel_url.rstrip('/') + '/streams'

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(streams_url, download=False)

            if 'entries' in info:
                for entry in info['entries']:
                    if not entry or 'id' not in entry:
                        continue

                    if entry.get('is_live', False):
                        video_id = entry.get('id')
                        title = entry.get('title')
                        self.logger.info(f"Live stream found in /streams: {video_id}")

                        return LiveStreamInfo(
                            video_id=video_id,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            title=title
                        )

        return None

    def _check_channel_page(self, channel_url: str) -> Optional[LiveStreamInfo]:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

            if 'entries' in info:
                for entry in info['entries']:
                    if not entry or 'id' not in entry:
                        continue

                    if entry.get('is_live', False):
                        video_id = entry.get('id')
                        title = entry.get('title')
                        self.logger.info(f"Live stream found on channel page: {video_id}")

                        return LiveStreamInfo(
                            video_id=video_id,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            title=title
                        )

        return None
