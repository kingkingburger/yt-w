"""Live stream monitor module."""

import logging
import time
from typing import Optional

from .config import Config
from .downloader import StreamDownloader
from .youtube_client import YouTubeClient


class LiveStreamMonitor:
    """Monitor YouTube channel for live streams and download them."""

    def __init__(
        self,
        config: Config,
        logger: logging.Logger,
        youtube_client: Optional[YouTubeClient] = None,
        downloader: Optional[StreamDownloader] = None
    ):
        """
        Initialize live stream monitor.

        Args:
            config: Configuration object
            logger: Logger instance
            youtube_client: Optional YouTubeClient instance
            downloader: Optional StreamDownloader instance
        """
        self.config = config
        self.logger = logger
        self.youtube_client = youtube_client or YouTubeClient(logger)
        self.downloader = downloader or StreamDownloader(
            download_directory=config.download_directory,
            download_format=config.download_format,
            logger=logger
        )
        self.is_downloading = False

    def start(self):
        """Start monitoring for live streams."""
        self._log_startup_info()

        while True:
            try:
                self._monitor_cycle()
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitor loop: {e}")
                time.sleep(self.config.check_interval_seconds)

    def _log_startup_info(self):
        """Log startup information."""
        self.logger.info("Starting live stream monitor...")
        self.logger.info(f"Channel URL: {self.config.channel_url}")
        self.logger.info(
            f"Check interval: {self.config.check_interval_seconds} seconds"
        )

    def _monitor_cycle(self):
        """Execute one monitoring cycle."""
        if self.is_downloading:
            time.sleep(self.config.check_interval_seconds)
            return

        self.logger.info("Checking for live stream...")
        is_live, stream_info = self.youtube_client.check_if_live(
            self.config.channel_url
        )

        if is_live and stream_info:
            self._handle_live_stream(stream_info.url)
        else:
            self.logger.info("No live stream found. Waiting...")

        time.sleep(self.config.check_interval_seconds)

    def _handle_live_stream(self, stream_url: str):
        """
        Handle detected live stream.

        Args:
            stream_url: URL of the live stream
        """
        self.logger.info(f"Live stream detected: {stream_url}")
        self.is_downloading = True

        try:
            success = self.downloader.download(
                stream_url=stream_url,
                filename_prefix="침착맨_라이브"
            )

            if success:
                self.logger.info("Download finished. Resuming monitoring...")
            else:
                self.logger.warning("Download failed. Resuming monitoring...")

        finally:
            self.is_downloading = False
