"""Per-channel monitoring worker contracts."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.channels.models import ChannelDTO, GlobalSettingsDTO
from src.yt_monitor.monitoring.worker import ChannelMonitorThread, _sanitize_name
from src.yt_monitor.youtube.client import LiveStreamInfo, YouTubeAuthError


class TestSanitizeName:
    """모듈 레벨 _sanitize_name 순수 함수 검증."""

    def test_removes_invalid_chars(self):
        sanitized = _sanitize_name('Test<>:"/\\|?*Channel')

        for char in '<>:"/\\|?*':
            assert char not in sanitized

    def test_preserves_valid_chars(self):
        assert _sanitize_name("Test Channel 123") == "Test Channel 123"


class TestChannelMonitorThread:
    """Test cases for ChannelMonitorThread class."""

    @pytest.fixture
    def mock_youtube_client(self) -> MagicMock:
        """Create mock YouTube client."""
        return MagicMock()

    @pytest.fixture
    def monitor_thread(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_youtube_client: MagicMock,
        initialized_logger,
    ) -> ChannelMonitorThread:
        """Create ChannelMonitorThread for testing."""
        return ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=mock_youtube_client,
        )

    def test_init_creates_channel_directory(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_youtube_client: MagicMock,
        initialized_logger,
        temp_dir: Path,
    ):
        """Test that __init__ creates channel-specific download directory."""
        ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=mock_youtube_client,
        )

        expected_dir = temp_dir / "downloads" / "live" / "Test Channel"
        assert expected_dir.exists()

    def test_start_and_stop_manage_thread_lifecycle(
        self, monitor_thread: ChannelMonitorThread
    ):
        """start()는 daemon thread를 시작하고 stop()은 실행 상태를 내린다."""
        monitor_thread.start()

        assert monitor_thread.is_running is True
        assert monitor_thread.thread is not None
        assert monitor_thread.thread.daemon is True

        monitor_thread.stop()
        assert monitor_thread.is_running is False

    def test_start_does_nothing_if_already_running(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that start() does nothing if already running."""
        monitor_thread.start()
        first_thread = monitor_thread.thread

        monitor_thread.start()

        assert monitor_thread.thread is first_thread

        monitor_thread.stop()

    def test_stop_terminates_active_downloader(
        self, monitor_thread: ChannelMonitorThread
    ):
        """stop()은 진행 중인 ffmpeg 다운로드를 끊기 위해 downloader.stop()을 호출한다."""
        with patch.object(monitor_thread.downloader, "stop") as mock_stop:
            monitor_thread.stop()

        mock_stop.assert_called_once()

    def test_monitor_cycle_checks_for_live(
        self,
        monitor_thread: ChannelMonitorThread,
        mock_youtube_client: MagicMock,
    ):
        """Test that _monitor_cycle checks for live stream."""
        mock_youtube_client.check_if_live.return_value = (False, None)

        monitor_thread._monitor_cycle()

        mock_youtube_client.check_if_live.assert_called_once_with(
            "https://www.youtube.com/@TestChannel"
        )

    def test_monitor_cycle_skips_when_downloading(
        self,
        monitor_thread: ChannelMonitorThread,
        mock_youtube_client: MagicMock,
    ):
        """Test that _monitor_cycle skips check when downloading."""
        monitor_thread.is_downloading = True

        monitor_thread._monitor_cycle()

        mock_youtube_client.check_if_live.assert_not_called()

    def test_monitor_cycle_handles_live_stream(
        self,
        monitor_thread: ChannelMonitorThread,
        mock_youtube_client: MagicMock,
    ):
        """Test that _monitor_cycle calls _handle_live_stream when live."""
        stream_info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Live Stream",
        )
        mock_youtube_client.check_if_live.return_value = (True, stream_info)

        with patch.object(monitor_thread, "_handle_live_stream") as mock_handle:
            monitor_thread._monitor_cycle()

            mock_handle.assert_called_once_with(
                "https://www.youtube.com/watch?v=abc123",
                "Live Stream",
            )

    def test_handle_live_stream_resets_flag_when_notifier_raises(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        initialized_logger,
    ):
        """notify_live_detected가 예외를 던져도 is_downloading은 False로 복구되어야 한다.

        과거에는 is_downloading=True 세팅이 try 블록 밖에 있어, 알림 호출 단계에서
        예외가 발생하면 flag가 영원히 True로 남아 채널 모니터링이 정지하는 버그가 있었다.
        """
        notifier = MagicMock()
        notifier.notify_live_detected.side_effect = RuntimeError("webhook 5xx")

        thread = ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=MagicMock(),
            notifier=notifier,
        )

        with pytest.raises(RuntimeError):
            thread._handle_live_stream(
                "https://www.youtube.com/watch?v=test",
                "Test Stream",
            )

        assert thread.is_downloading is False


class TestChannelMonitorThreadNotifications:
    """알림 호출 검증 — 라이브 감지/다운로드/에러 이벤트가 Discord에 전송되는지.

    notifier를 생성자에 직접 주입하므로 patch 중첩 없이 assert만 호출하면 된다.
    """

    @pytest.fixture
    def mock_notifier(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def monitor_thread(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ) -> ChannelMonitorThread:
        return ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=MagicMock(),
            notifier=mock_notifier,
        )

    def test_handle_live_stream_sends_live_detected_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """라이브 감지 시 notify_live_detected가 호출된다."""
        with patch.object(monitor_thread.downloader, "download", return_value=True):
            monitor_thread._handle_live_stream(
                "https://youtube.com/watch?v=abc", "방송 제목"
            )

        mock_notifier.notify_live_detected.assert_called_once_with(
            channel_name="Test Channel",
            stream_url="https://youtube.com/watch?v=abc",
            title="방송 제목",
        )

    def test_handle_live_stream_success_sends_download_complete_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """다운로드 성공 시 notify_download_complete가 호출된다."""
        with patch.object(monitor_thread.downloader, "download", return_value=True):
            monitor_thread._handle_live_stream(
                "https://youtube.com/watch?v=abc", "방송 제목"
            )

        mock_notifier.notify_download_complete.assert_called_once_with(
            channel_name="Test Channel",
            title="방송 제목",
        )
        mock_notifier.notify_download_failed.assert_not_called()
        assert monitor_thread.is_downloading is False

    def test_handle_live_stream_failure_sends_download_failed_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """다운로드 실패(success=False) 시 notify_download_failed가 호출된다."""
        with patch.object(monitor_thread.downloader, "download", return_value=False):
            monitor_thread._handle_live_stream(
                "https://youtube.com/watch?v=abc", "방송 제목"
            )

        mock_notifier.notify_download_failed.assert_called_once_with(
            channel_name="Test Channel",
            error_message="다운로드가 실패했습니다 (success=False)",
        )
        mock_notifier.notify_download_complete.assert_not_called()
        assert monitor_thread.is_downloading is False

    def test_handle_live_stream_exception_sends_download_failed_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """다운로드 예외 발생 시 notify_download_failed가 호출된다."""
        with patch.object(
            monitor_thread.downloader,
            "download",
            side_effect=Exception("ffmpeg crashed"),
        ):
            with pytest.raises(Exception):
                monitor_thread._handle_live_stream(
                    "https://youtube.com/watch?v=abc", "방송 제목"
                )

        mock_notifier.notify_download_failed.assert_called_once_with(
            channel_name="Test Channel",
            error_message="ffmpeg crashed",
        )
        assert monitor_thread.is_downloading is False

    def test_monitor_loop_exception_sends_error_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """_monitor_cycle 예외 시 notify_error가 호출된다."""

        def cycle_side_effect():
            monitor_thread.is_running = False
            raise Exception("API timeout")

        with patch.object(
            monitor_thread, "_monitor_cycle", side_effect=cycle_side_effect
        ):
            with patch("src.yt_monitor.monitoring.worker.time.sleep"):
                monitor_thread.is_running = True
                monitor_thread._monitor_loop()

        mock_notifier.notify_error.assert_called_once_with(
            channel_name="Test Channel",
            error_message="API timeout",
        )

    def test_monitor_loop_auth_error_respects_cooldown(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ):
        """쿨다운 내 반복되는 YouTubeAuthError는 1번만 알림을 보낸다."""
        from src.yt_monitor.monitoring.cooldown import AlertCooldown

        # 세 번 모두 쿨다운(1800초) 내 시각 — 첫 번째만 통과
        time_sequence = iter([1000.0, 1005.0, 1010.0])
        thread = ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=MagicMock(),
            notifier=mock_notifier,
            auth_alert_cooldown=AlertCooldown(
                cooldown_seconds=1800.0, clock=lambda: next(time_sequence)
            ),
        )

        call_count = 0

        def cycle_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                thread.is_running = False
            raise YouTubeAuthError("Sign in to confirm you're not a bot")

        with patch.object(thread, "_monitor_cycle", side_effect=cycle_side_effect):
            with patch("src.yt_monitor.monitoring.worker.time.sleep"):
                thread.is_running = True
                thread._monitor_loop()

        mock_notifier.notify_bot_detection.assert_called_once_with(
            channel_name="Test Channel",
            detail="Sign in to confirm you're not a bot",
        )
        mock_notifier.notify_error.assert_not_called()

    def test_monitor_loop_auth_error_after_cooldown_sends_again(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ):
        """쿨다운 경과 후 재발생하면 다시 알림을 보낸다."""
        from src.yt_monitor.monitoring.cooldown import AlertCooldown

        # 첫 호출 t=1000, 두 번째 t=3000 (2000초 경과 > 1800초 쿨다운)
        time_sequence = iter([1000.0, 3000.0])
        thread = ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=MagicMock(),
            notifier=mock_notifier,
            auth_alert_cooldown=AlertCooldown(
                cooldown_seconds=1800.0, clock=lambda: next(time_sequence)
            ),
        )

        call_count = 0

        def cycle_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                thread.is_running = False
            raise YouTubeAuthError("Sign in to confirm you're not a bot")

        with patch.object(thread, "_monitor_cycle", side_effect=cycle_side_effect):
            with patch("src.yt_monitor.monitoring.worker.time.sleep"):
                thread.is_running = True
                thread._monitor_loop()

        assert mock_notifier.notify_bot_detection.call_count == 2
