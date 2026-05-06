"""Multi-channel live stream monitor module."""

import signal
import time
import threading
from typing import Dict, Optional
from pathlib import Path

from . import StreamDownloader
from .alert_cooldown import AlertCooldown
from .channel_manager import ChannelManager, ChannelDTO, GlobalSettingsDTO
from .discord_notifier import DiscordNotifier, get_notifier
from .logger import Logger
from .monitor_status import write_monitor_status
from .youtube_client import YouTubeClient, YouTubeAuthError


_AUTH_ALERT_COOLDOWN_SECONDS: float = 1800.0  # 30분 쿨다운으로 알림 폭주 방지


def _sanitize_name(name: str) -> str:
    """채널 이름에서 파일시스템 예약 문자를 '_'로 치환한다."""
    invalid_chars = '<>:"/\\|?*'
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, "_")
    return sanitized


class ChannelMonitorThread:
    """Monitor thread for a single channel."""

    def __init__(
        self,
        channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        youtube_client: YouTubeClient,
        notifier: Optional[DiscordNotifier] = None,
        auth_alert_cooldown: Optional[AlertCooldown] = None,
    ):
        """
        Args:
            channel: 모니터할 채널
            global_settings: 전역 설정
            youtube_client: 라이브 감지용 YouTube 클라이언트
            notifier: Discord 알림 클라이언트 (None이면 모듈 기본값 사용)
            auth_alert_cooldown: 봇 감지 알림 쿨다운 (None이면 기본 30분)
        """
        self.channel = channel
        self.global_settings = global_settings
        self.youtube_client = youtube_client
        self.logger = Logger.get()
        self.is_running = False
        self.is_downloading = False
        self.thread: Optional[threading.Thread] = None
        self._notifier: DiscordNotifier = notifier or get_notifier()
        self._auth_alert_cooldown: AlertCooldown = (
            auth_alert_cooldown
            or AlertCooldown(cooldown_seconds=_AUTH_ALERT_COOLDOWN_SECONDS)
        )

        channel_download_dir = (
            Path(global_settings.download_directory)
            / "live"
            / _sanitize_name(channel.name)
        )
        channel_download_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = StreamDownloader(
            download_directory=str(channel_download_dir),
            download_format=channel.download_format,
            split_mode=global_settings.split_mode,
            split_time_minutes=global_settings.split_time_minutes,
            split_size_mb=global_settings.split_size_mb,
        )

    def start(self) -> None:
        """Start monitoring thread."""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"Started monitoring channel: {self.channel.name}")

    def stop(self) -> None:
        """Stop monitoring thread.

        진행 중인 ffmpeg 다운로드도 함께 끊어 좀비를 막는다.
        downloader.stop()은 진행 중이 아니면 no-op.
        """
        self.is_running = False
        self.downloader.stop()
        if self.thread:
            self.thread.join(timeout=5.0)
        self.logger.info(f"Stopped monitoring channel: {self.channel.name}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop for this channel."""
        while self.is_running:
            try:
                self._monitor_cycle()
            except YouTubeAuthError as e:
                self.logger.error(
                    f"[{self.channel.name}] YouTube 봇 감지로 라이브 확인 실패: {e}"
                )
                self._maybe_notify_auth_error(str(e))
            except Exception as e:
                self.logger.error(f"Error monitoring {self.channel.name}: {e}")
                self._notifier.notify_error(
                    channel_name=self.channel.name,
                    error_message=str(e),
                )

            time.sleep(self.global_settings.check_interval_seconds)

    def _maybe_notify_auth_error(self, error_message: str) -> None:
        """쿨다운을 통과한 경우에만 봇 감지 알림을 전송한다."""
        if not self._auth_alert_cooldown.try_acquire():
            return
        self._notifier.notify_bot_detection(
            channel_name=self.channel.name,
            detail=error_message,
        )

    def _monitor_cycle(self) -> None:
        """Single monitoring cycle."""
        if self.is_downloading:
            return

        self.logger.info(f"[{self.channel.name}] Checking for live stream...")

        is_live, stream_info = self.youtube_client.check_if_live(self.channel.url)

        if is_live and stream_info:
            self._handle_live_stream(stream_info.url, stream_info.title or "라이브")
        else:
            self.logger.info(f"[{self.channel.name}] No live stream found")

    def _handle_live_stream(self, stream_url: str, title: str) -> None:
        """감지된 라이브 스트림을 다운로드하고 결과를 알린다."""
        self.logger.info(f"[{self.channel.name}] Live stream detected: {stream_url}")
        self.is_downloading = True

        self._notifier.notify_live_detected(
            channel_name=self.channel.name,
            stream_url=stream_url,
            title=title,
        )

        try:
            success = self.downloader.download(
                stream_url=stream_url, filename_prefix=f"{self.channel.name}_라이브"
            )

            if success:
                self.logger.info(f"[{self.channel.name}] Download finished")
                self._notifier.notify_download_complete(
                    channel_name=self.channel.name,
                    title=title,
                )
            else:
                self.logger.warning(f"[{self.channel.name}] Download failed")
                self._notifier.notify_download_failed(
                    channel_name=self.channel.name,
                    error_message="다운로드가 실패했습니다 (success=False)",
                )

        except Exception as e:
            self._notifier.notify_download_failed(
                channel_name=self.channel.name,
                error_message=str(e),
            )
            raise

        finally:
            self.is_downloading = False


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
        self.is_running = False
        self._notifier: DiscordNotifier = notifier or get_notifier()

    def _write_status(self, state: str, message: str = "") -> None:
        """Publish daemon status for yt-web through the shared logs volume."""
        try:
            settings = self.channel_manager.get_global_settings()
            total_channels = len(self.channel_manager.list_channels())
            write_monitor_status(
                settings.log_file,
                state=state,
                active_channels=len(self.monitor_threads),
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
            monitor_thread = self._build_channel_thread(channel, global_settings)
            monitor_thread.start()
            self.monitor_threads[channel.id] = monitor_thread

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

        for monitor_thread in self.monitor_threads.values():
            monitor_thread.stop()

        self.monitor_threads.clear()
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

        if channel.id in self.monitor_threads:
            self.logger.warning(f"Channel {channel.name} is already being monitored")
            return

        global_settings = self.channel_manager.get_global_settings()

        monitor_thread = self._build_channel_thread(channel, global_settings)
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
