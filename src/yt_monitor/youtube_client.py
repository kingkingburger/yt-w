"""YouTube API client module for live stream detection."""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import yt_dlp


@dataclass
class LiveStreamInfo:
    """Information about a detected live stream."""

    video_id: str
    url: str
    title: Optional[str] = None

    def __post_init__(self):
        """Ensure URL is properly formatted."""
        if not self.url.startswith('http'):
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"


class YouTubeClient:
    """Client for interacting with YouTube to detect live streams."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize YouTube client.

        Args:
            logger: Logger instance for logging
        """
        self.logger = logger or logging.getLogger(__name__)

    def check_if_live(self, channel_url: str) -> Tuple[bool, Optional[LiveStreamInfo]]:
        """
        Check if the channel is currently live streaming.

        This method tries multiple detection strategies:
        1. Check /live endpoint
        2. Check /streams tab
        3. Check main channel page

        Args:
            channel_url: YouTube channel URL

        Returns:
            Tuple of (is_live, stream_info)
            - is_live: True if live stream detected
            - stream_info: LiveStreamInfo object if live, None otherwise
        """
        # Try multiple detection methods
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
        """
        Check /live endpoint for active stream.

        Args:
            channel_url: YouTube channel URL

        Returns:
            LiveStreamInfo if live stream found, None otherwise
        """
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
        """
        Check /streams tab for active stream.

        Args:
            channel_url: YouTube channel URL

        Returns:
            LiveStreamInfo if live stream found, None otherwise
        """
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
        """
        Check main channel page for active stream.

        Args:
            channel_url: YouTube channel URL

        Returns:
            LiveStreamInfo if live stream found, None otherwise
        """
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
