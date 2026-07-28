"""Per-channel live detection and recording worker."""

import threading
import time
from pathlib import Path
from typing import Optional

from ..channels.models import ChannelDTO, GlobalSettingsDTO
from ..logging import Logger
from ..media.merge import VideoExtensions, merge_completed_stream_files
from ..media.stream_download import StreamDownloader
from ..notifications.discord import DiscordNotifier, get_notifier
from ..youtube.client import YouTubeAuthError, YouTubeClient
from .cooldown import AlertCooldown


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
        self._active_stream_url: Optional[str] = None
        self._completed_stream_files: set[Path] = set()
        self._notifier: DiscordNotifier = notifier or get_notifier()
        self._auth_alert_cooldown: AlertCooldown = (
            auth_alert_cooldown
            or AlertCooldown(cooldown_seconds=_AUTH_ALERT_COOLDOWN_SECONDS)
        )

        self._channel_download_dir = (
            Path(global_settings.download_directory)
            / "live"
            / _sanitize_name(channel.name)
        )
        self._channel_download_dir.mkdir(parents=True, exist_ok=True)

        self.downloader = StreamDownloader(
            download_directory=str(self._channel_download_dir),
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
            except YouTubeAuthError as error:
                self.logger.error(
                    f"[{self.channel.name}] YouTube 봇 감지로 라이브 확인 실패: {error}"
                )
                self._maybe_notify_auth_error(str(error))
            except Exception as error:
                self.logger.error(f"Error monitoring {self.channel.name}: {error}")
                self._notifier.notify_error(
                    channel_name=self.channel.name,
                    error_message=str(error),
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
            self._activate_stream(stream_info.url)
            self._handle_live_stream(stream_info.url, stream_info.title or "라이브")
        else:
            self._finish_active_stream()
            self.logger.info(f"[{self.channel.name}] No live stream found")

    def _activate_stream(self, stream_url: str) -> None:
        """새 방송이면 직전 방송을 먼저 병합하고 추적 대상을 바꾼다."""
        if (
            self._active_stream_url is not None
            and self._active_stream_url != stream_url
        ):
            self._finish_active_stream()
        self._active_stream_url = stream_url

    def _list_channel_video_files(self) -> set[Path]:
        """현재 채널 다운로드 폴더의 완성된 영상 파일 경로를 반환한다."""
        return {
            path.resolve()
            for path in self._channel_download_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VideoExtensions
        }

    def _finish_active_stream(self) -> None:
        """방송 종료까지 누적한 완료 파일을 이름순으로 자동 병합한다."""
        if self._active_stream_url is None:
            return

        completed_files = sorted(
            self._completed_stream_files,
            key=lambda path: (path.name.casefold(), str(path).casefold()),
        )
        self._active_stream_url = None
        self._completed_stream_files = set()
        if not completed_files:
            return

        self.logger.info(
            f"[{self.channel.name}] Broadcast ended; auto-merging "
            f"{len(completed_files)} completed file(s)"
        )
        output_path = merge_completed_stream_files(
            Path(self.global_settings.download_directory),
            completed_files,
        )
        self.logger.info(
            f"[{self.channel.name}] Automatic merge finished: {output_path}"
        )

    def _handle_live_stream(self, stream_url: str, title: str) -> None:
        """감지된 라이브 스트림을 다운로드하고 결과를 알린다."""
        self.logger.info(f"[{self.channel.name}] Live stream detected: {stream_url}")
        self.is_downloading = True
        files_before_download = self._list_channel_video_files()
        try:
            self._notifier.notify_live_detected(
                channel_name=self.channel.name,
                stream_url=stream_url,
                title=title,
            )

            try:
                success = self.downloader.download(
                    stream_url=stream_url,
                    filename_prefix=f"{self.channel.name}_라이브",
                )
            except Exception as error:
                self._notifier.notify_download_failed(
                    channel_name=self.channel.name,
                    error_message=str(error),
                )
                raise

            if success:
                self._completed_stream_files.update(
                    self._list_channel_video_files() - files_before_download
                )
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
        finally:
            self.is_downloading = False
