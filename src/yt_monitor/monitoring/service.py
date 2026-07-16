"""Multi-channel live stream monitor service."""

import signal
import threading
import time
from typing import Dict, Optional

from ..channels.models import ChannelDTO, GlobalSettingsDTO
from ..channels.repository import ChannelManager
from ..logging import Logger
from ..notifications.discord import DiscordNotifier, get_notifier
from ..youtube.client import YouTubeClient
from .status import write_monitor_status
from .worker import ChannelMonitorThread


class MultiChannelMonitor:
    """Monitor multiple YouTube channels simultaneously for live streams."""

    def __init__(
        self,
        channel_manager: Optional[ChannelManager] = None,
        youtube_client: Optional[YouTubeClient] = None,
        notifier: Optional[DiscordNotifier] = None,
    ):
        """
        Args:
            channel_manager: 채널 저장소
            youtube_client: YouTube 클라이언트
            notifier: Discord 알림 클라이언트 (None이면 모듈 기본값 사용)
        """
        self.channel_manager = channel_manager or ChannelManager()
        self.youtube_client = youtube_client or YouTubeClient()
        self.logger = Logger.get()
        self.monitor_threads: Dict[str, ChannelMonitorThread] = {}
        self._monitor_threads_lock: threading.Lock = threading.Lock()
        self.is_running = False
        self._notifier: DiscordNotifier = notifier or get_notifier()

    def _write_status(self, state: str, message: str = "") -> None:
        """Publish daemon status for yt-web through the shared logs volume."""
        try:
            settings = self.channel_manager.get_global_settings()
            total_channels = len(self.channel_manager.list_channels())
            with self._monitor_threads_lock:
                active_channels = len(self.monitor_threads)
            write_monitor_status(
                settings.log_file,
                state=state,
                active_channels=active_channels,
                total_channels=total_channels,
                message=message,
            )
        except Exception as error:
            self.logger.warning(f"Failed to write monitor status: {error}")

    def _build_channel_thread(
        self,
        channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
    ) -> ChannelMonitorThread:
        """채널별 모니터 스레드를 생성한다 (테스트에서 오버라이드 가능)."""
        return ChannelMonitorThread(
            channel=channel,
            global_settings=global_settings,
            youtube_client=self.youtube_client,
            notifier=self._notifier,
        )

    def _thread_needs_restart(
        self,
        monitor_thread: ChannelMonitorThread,
        channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
    ) -> bool:
        """Return whether a running thread no longer matches channel config."""
        return (
            monitor_thread.channel.name != channel.name
            or monitor_thread.channel.url != channel.url
            or monitor_thread.channel.download_format != channel.download_format
            or monitor_thread.global_settings != global_settings
        )

    def _start_channel_monitoring(
        self,
        channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
    ) -> None:
        monitor_thread = self._build_channel_thread(channel, global_settings)

        with self._monitor_threads_lock:
            if channel.id in self.monitor_threads:
                self.logger.warning(f"Channel {channel.name} is already being monitored")
                return
            self.monitor_threads[channel.id] = monitor_thread

        monitor_thread.start()

    def _sync_channel_monitors(self) -> None:
        """Reconcile running monitor threads with the shared channels file."""
        if not self.is_running:
            return

        channels = self.channel_manager.list_channels(enabled_only=True)
        channels_by_id = {channel.id: channel for channel in channels}
        global_settings = self.channel_manager.get_global_settings()

        with self._monitor_threads_lock:
            running_threads = list(self.monitor_threads.items())

        for channel_id, monitor_thread in running_threads:
            channel = channels_by_id.get(channel_id)
            if channel is None:
                self.logger.info(
                    f"Stopping monitor for disabled or removed channel: {channel_id}"
                )
                self.remove_channel_and_stop_monitoring(channel_id)
                continue

            if self._thread_needs_restart(monitor_thread, channel, global_settings):
                self.logger.info(f"Restarting monitor for updated channel: {channel.name}")
                self.remove_channel_and_stop_monitoring(channel_id)
                self._start_channel_monitoring(channel, global_settings)

        with self._monitor_threads_lock:
            running_channel_ids = set(self.monitor_threads)

        for channel in channels:
            if channel.id not in running_channel_ids:
                self.logger.info(f"Starting monitor for newly enabled channel: {channel.name}")
                self._start_channel_monitoring(channel, global_settings)

    def start(self) -> None:
        """Start monitoring all enabled channels."""
        self.logger.info("Starting multi-channel monitor...")

        channels = self.channel_manager.list_channels(enabled_only=True)

        if not channels:
            self.logger.warning("No enabled channels found to monitor")
            self._write_status("stopped", "no enabled channels")
            return

        global_settings = self.channel_manager.get_global_settings()

        self.logger.info(f"Found {len(channels)} channels to monitor:")
        for channel in channels:
            self.logger.info(f"  - {channel.name}: {channel.url}")

        self.is_running = True

        for channel in channels:
            self._start_channel_monitoring(channel, global_settings)

        self.logger.info("All channel monitors started")
        self._write_status("running", "monitor daemon running")
        self._notifier.notify_monitor_started(channel_count=len(channels))

        # SIGTERM은 메인 스레드에서만 등록 가능 — 웹 라우트가 백그라운드
        # 스레드에서 start()를 호출하면 signal.signal()이 ValueError를 던진다.
        if threading.current_thread() is threading.main_thread():
            def handle_sigterm(signum: int, frame: object) -> None:
                self.logger.info("Received SIGTERM signal")
                self._notifier.notify_monitor_stopped(reason="docker stop (SIGTERM)")
                self.stop()

            signal.signal(signal.SIGTERM, handle_sigterm)

        try:
            while self.is_running:
                self._sync_channel_monitors()
                self._write_status("running", "monitor daemon running")
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
            self._notifier.notify_monitor_stopped(reason="shutdown signal")
            self.stop()

    def stop(self) -> None:
        """Stop monitoring all channels."""
        self.logger.info("Stopping all channel monitors...")

        self.is_running = False

        with self._monitor_threads_lock:
            threads_to_stop = list(self.monitor_threads.values())
            self.monitor_threads.clear()

        for monitor_thread in threads_to_stop:
            monitor_thread.stop()

        self.logger.info("Multi-channel monitor stopped")
        self._write_status("stopped", "monitor daemon stopped")

    def add_channel_and_start_monitoring(self, channel: ChannelDTO) -> None:
        """
        Add a new channel and start monitoring it immediately.

        Args:
            channel: Channel to add and monitor
        """
        if not self.is_running:
            return

        global_settings = self.channel_manager.get_global_settings()
        self._start_channel_monitoring(channel, global_settings)

    def remove_channel_and_stop_monitoring(self, channel_id: str) -> None:
        """
        Remove a channel and stop monitoring it.

        Args:
            channel_id: ID of channel to remove
        """
        with self._monitor_threads_lock:
            monitor_thread = self.monitor_threads.pop(channel_id, None)

        if monitor_thread is not None:
            monitor_thread.stop()
