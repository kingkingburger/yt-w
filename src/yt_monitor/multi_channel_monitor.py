"""Multi-channel live stream monitor module."""

import time
import threading
from typing import Dict, Optional
from pathlib import Path

from .channel_manager import ChannelManager, ChannelDTO, GlobalSettingsDTO
from .downloader import StreamDownloader
from .logger import Logger
from .youtube_client import YouTubeClient


class ChannelMonitorThread:
    """Monitor thread for a single channel."""

    def __init__(
        self,
        channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        youtube_client: YouTubeClient,
    ):
        """
        Initialize channel monitor thread.

        Args:
            channel: Channel to monitor
            global_settings: Global settings for monitoring
            youtube_client: YouTube client for live detection
        """
        self.channel = channel
        self.global_settings = global_settings
        self.youtube_client = youtube_client
        self.logger = Logger.get()
        self.is_running = False
        self.is_downloading = False
        self.thread: Optional[threading.Thread] = None

        # Create channel-specific download directory
        channel_download_dir = Path(global_settings.download_directory) / self._sanitize_name(channel.name)
        channel_download_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = StreamDownloader(
            download_directory=str(channel_download_dir),
            download_format=channel.download_format,
            split_mode=global_settings.split_mode,
            split_time_minutes=global_settings.split_time_minutes,
            split_size_mb=global_settings.split_size_mb,
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize channel name for use as directory name.

        Args:
            name: Channel name

        Returns:
            Sanitized name safe for filesystem
        """
        # Remove invalid filesystem characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "_")
        return sanitized

    def start(self) -> None:
        """Start monitoring thread."""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"Started monitoring channel: {self.channel.name}")

    def stop(self) -> None:
        """Stop monitoring thread."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        self.logger.info(f"Stopped monitoring channel: {self.channel.name}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop for this channel."""
        while self.is_running:
            try:
                self._monitor_cycle()
            except Exception as e:
                self.logger.error(
                    f"Error monitoring {self.channel.name}: {e}"
                )

            time.sleep(self.global_settings.check_interval_seconds)

    def _monitor_cycle(self) -> None:
        """Single monitoring cycle."""
        if self.is_downloading:
            return

        self.logger.info(f"[{self.channel.name}] Checking for live stream...")

        is_live, stream_info = self.youtube_client.check_if_live(
            self.channel.url
        )

        if is_live and stream_info:
            self._handle_live_stream(stream_info.url, stream_info.title or "라이브")
        else:
            self.logger.info(f"[{self.channel.name}] No live stream found")

    def _handle_live_stream(self, stream_url: str, title: str) -> None:
        """
        Handle detected live stream.

        Args:
            stream_url: URL of live stream
            title: Title of live stream
        """
        self.logger.info(
            f"[{self.channel.name}] Live stream detected: {stream_url}"
        )
        self.is_downloading = True

        try:
            success = self.downloader.download(
                stream_url=stream_url,
                filename_prefix=f"{self.channel.name}_라이브"
            )

            if success:
                self.logger.info(
                    f"[{self.channel.name}] Download finished"
                )
            else:
                self.logger.warning(
                    f"[{self.channel.name}] Download failed"
                )

        finally:
            self.is_downloading = False


class MultiChannelMonitor:
    """Monitor multiple YouTube channels simultaneously for live streams."""

    def __init__(
        self,
        channel_manager: Optional[ChannelManager] = None,
        youtube_client: Optional[YouTubeClient] = None,
    ):
        """
        Initialize multi-channel monitor.

        Args:
            channel_manager: Channel manager instance
            youtube_client: YouTube client instance
        """
        self.channel_manager = channel_manager or ChannelManager()
        self.youtube_client = youtube_client or YouTubeClient()
        self.logger = Logger.get()
        self.monitor_threads: Dict[str, ChannelMonitorThread] = {}
        self.is_running = False

    def start(self) -> None:
        """Start monitoring all enabled channels."""
        self.logger.info("Starting multi-channel monitor...")

        channels = self.channel_manager.list_channels(enabled_only=True)

        if not channels:
            self.logger.warning("No enabled channels found to monitor")
            return

        global_settings = self.channel_manager.get_global_settings()

        self.logger.info(f"Found {len(channels)} channels to monitor:")
        for channel in channels:
            self.logger.info(f"  - {channel.name}: {channel.url}")

        self.is_running = True

        # Start monitoring thread for each channel
        for channel in channels:
            monitor_thread = ChannelMonitorThread(
                channel=channel,
                global_settings=global_settings,
                youtube_client=self.youtube_client,
            )
            monitor_thread.start()
            self.monitor_threads[channel.id] = monitor_thread

        self.logger.info("All channel monitors started")

        # Keep main thread alive
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
            self.stop()

    def stop(self) -> None:
        """Stop monitoring all channels."""
        self.logger.info("Stopping all channel monitors...")

        self.is_running = False

        for monitor_thread in self.monitor_threads.values():
            monitor_thread.stop()

        self.monitor_threads.clear()
        self.logger.info("Multi-channel monitor stopped")

    def add_channel_and_start_monitoring(self, channel: ChannelDTO) -> None:
        """
        Add a new channel and start monitoring it immediately.

        Args:
            channel: Channel to add and monitor
        """
        if not self.is_running:
            return

        if channel.id in self.monitor_threads:
            self.logger.warning(
                f"Channel {channel.name} is already being monitored"
            )
            return

        global_settings = self.channel_manager.get_global_settings()

        monitor_thread = ChannelMonitorThread(
            channel=channel,
            global_settings=global_settings,
            youtube_client=self.youtube_client,
        )
        monitor_thread.start()
        self.monitor_threads[channel.id] = monitor_thread

    def remove_channel_and_stop_monitoring(self, channel_id: str) -> None:
        """
        Remove a channel and stop monitoring it.

        Args:
            channel_id: ID of channel to remove
        """
        if channel_id in self.monitor_threads:
            self.monitor_threads[channel_id].stop()
            del self.monitor_threads[channel_id]
