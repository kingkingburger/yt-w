"""Tests for multi_channel_monitor module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.channel_manager import ChannelDTO, GlobalSettingsDTO, ChannelManager
from src.yt_monitor.multi_channel_monitor import (
    ChannelMonitorThread,
    MultiChannelMonitor,
    _sanitize_name,
)
from src.yt_monitor.youtube_client import LiveStreamInfo, YouTubeAuthError


@pytest.fixture
def sample_channel() -> ChannelDTO:
    return ChannelDTO(
        id="test-channel-id",
        name="Test Channel",
        url="https://www.youtube.com/@TestChannel",
        enabled=True,
    )


@pytest.fixture
def global_settings(temp_dir: Path) -> GlobalSettingsDTO:
    return GlobalSettingsDTO(
        check_interval_seconds=1,
        download_directory=str(temp_dir / "downloads"),
        log_file=str(temp_dir / "test.log"),
        split_mode="time",
        split_time_minutes=30,
    )


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

    def test_start_sets_is_running(self, monitor_thread: ChannelMonitorThread):
        """Test that start() sets is_running to True."""
        monitor_thread.start()

        assert monitor_thread.is_running is True

        monitor_thread.stop()

    def test_start_creates_thread(self, monitor_thread: ChannelMonitorThread):
        """Test that start() creates a daemon thread."""
        monitor_thread.start()

        assert monitor_thread.thread is not None
        assert monitor_thread.thread.daemon is True

        monitor_thread.stop()

    def test_start_does_nothing_if_already_running(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that start() does nothing if already running."""
        monitor_thread.start()
        first_thread = monitor_thread.thread

        monitor_thread.start()

        assert monitor_thread.thread is first_thread

        monitor_thread.stop()

    def test_stop_sets_is_running_false(self, monitor_thread: ChannelMonitorThread):
        """Test that stop() sets is_running to False."""
        monitor_thread.start()
        monitor_thread.stop()

        assert monitor_thread.is_running is False

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

    def test_handle_live_stream_resets_is_downloading_after_success(
        self, monitor_thread: ChannelMonitorThread
    ):
        """_handle_live_stream 정상 완료 후 is_downloading이 False로 복구된다."""
        with patch.object(monitor_thread.downloader, "download", return_value=True):
            monitor_thread._handle_live_stream(
                "https://www.youtube.com/watch?v=test",
                "Test Stream",
            )

        assert monitor_thread.is_downloading is False

    def test_handle_live_stream_resets_flag_on_failure(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that _handle_live_stream resets flag even on failure."""
        with patch.object(monitor_thread.downloader, "download", return_value=False):
            monitor_thread._handle_live_stream(
                "https://www.youtube.com/watch?v=test",
                "Test Stream",
            )

        assert monitor_thread.is_downloading is False

    def test_handle_live_stream_resets_flag_on_exception(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that _handle_live_stream resets flag even on exception."""
        with patch.object(
            monitor_thread.downloader,
            "download",
            side_effect=Exception("Error"),
        ):
            try:
                monitor_thread._handle_live_stream(
                    "https://www.youtube.com/watch?v=test",
                    "Test Stream",
                )
            except Exception:
                pass

        assert monitor_thread.is_downloading is False


class TestMultiChannelMonitor:
    """Test cases for MultiChannelMonitor class."""

    @pytest.fixture
    def mock_channel_manager(self, temp_dir: Path) -> MagicMock:
        """Create mock channel manager."""
        manager = MagicMock(spec=ChannelManager)
        manager.list_channels.return_value = []
        manager.get_global_settings.return_value = GlobalSettingsDTO(
            download_directory=str(temp_dir / "downloads"),
            log_file=str(temp_dir / "test.log"),
        )
        return manager

    @pytest.fixture
    def mock_youtube_client(self) -> MagicMock:
        """Create mock YouTube client."""
        return MagicMock()

    @pytest.fixture
    def multi_monitor(
        self,
        mock_channel_manager: MagicMock,
        mock_youtube_client: MagicMock,
        initialized_logger,
    ) -> MultiChannelMonitor:
        """Create MultiChannelMonitor for testing."""
        return MultiChannelMonitor(
            channel_manager=mock_channel_manager,
            youtube_client=mock_youtube_client,
        )

    def test_init_with_defaults(self, initialized_logger):
        """Test MultiChannelMonitor initialization with defaults."""
        with patch("src.yt_monitor.multi_channel_monitor.ChannelManager"):
            with patch("src.yt_monitor.multi_channel_monitor.YouTubeClient"):
                monitor = MultiChannelMonitor()

                assert monitor.channel_manager is not None
                assert monitor.youtube_client is not None
                assert monitor.is_running is False

    def test_start_with_no_channels(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
    ):
        """Test start() when no enabled channels exist."""
        mock_channel_manager.list_channels.return_value = []

        multi_monitor.start()

        assert multi_monitor.is_running is False

    def test_start_creates_monitor_threads(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
        temp_dir: Path,
    ):
        """실제 start() 경로가 채널마다 monitor thread를 생성·등록한다."""
        channels = [
            ChannelDTO(
                id="channel1",
                name="Channel 1",
                url="https://www.youtube.com/@Channel1",
            ),
            ChannelDTO(
                id="channel2",
                name="Channel 2",
                url="https://www.youtube.com/@Channel2",
            ),
        ]
        mock_channel_manager.list_channels.return_value = channels
        multi_monitor.youtube_client.check_if_live.return_value = (False, None)

        def exit_keep_alive_loop(sig, handler):
            # SIGTERM 핸들러 등록 지점에서 메인 while 루프를 즉시 종료시킨다
            multi_monitor.is_running = False

        with patch("src.yt_monitor.multi_channel_monitor.get_notifier"):
            with patch("src.yt_monitor.multi_channel_monitor.signal") as mock_sig:
                mock_sig.signal.side_effect = exit_keep_alive_loop
                with patch("src.yt_monitor.multi_channel_monitor.time") as mock_time:
                    mock_time.sleep = MagicMock()
                    multi_monitor.start()

        try:
            assert len(multi_monitor.monitor_threads) == 2
            assert "channel1" in multi_monitor.monitor_threads
            assert "channel2" in multi_monitor.monitor_threads
        finally:
            multi_monitor.stop()

    def test_stop_clears_monitor_threads(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """Test that stop() clears all monitor threads."""
        # Add some mock threads
        mock_thread1 = MagicMock()
        mock_thread2 = MagicMock()
        multi_monitor.monitor_threads = {
            "channel1": mock_thread1,
            "channel2": mock_thread2,
        }
        multi_monitor.is_running = True

        multi_monitor.stop()

        assert multi_monitor.is_running is False
        assert len(multi_monitor.monitor_threads) == 0
        mock_thread1.stop.assert_called_once()
        mock_thread2.stop.assert_called_once()

    def test_add_channel_and_start_monitoring(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
        temp_dir: Path,
    ):
        """Test adding a channel and starting monitoring for it."""
        multi_monitor.is_running = True
        channel = ChannelDTO(
            id="new-channel",
            name="New Channel",
            url="https://www.youtube.com/@NewChannel",
        )

        multi_monitor.add_channel_and_start_monitoring(channel)

        assert "new-channel" in multi_monitor.monitor_threads

    def test_add_channel_does_nothing_when_not_running(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """Test that add_channel_and_start_monitoring does nothing when not running."""
        multi_monitor.is_running = False
        channel = ChannelDTO(
            id="new-channel",
            name="New Channel",
            url="https://www.youtube.com/@NewChannel",
        )

        multi_monitor.add_channel_and_start_monitoring(channel)

        assert len(multi_monitor.monitor_threads) == 0

    def test_add_channel_does_nothing_for_existing_channel(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """Test that add_channel_and_start_monitoring skips existing channels."""
        multi_monitor.is_running = True
        existing_thread = MagicMock()
        multi_monitor.monitor_threads["existing-channel"] = existing_thread

        channel = ChannelDTO(
            id="existing-channel",
            name="Existing Channel",
            url="https://www.youtube.com/@ExistingChannel",
        )

        multi_monitor.add_channel_and_start_monitoring(channel)

        assert multi_monitor.monitor_threads["existing-channel"] is existing_thread

    def test_remove_channel_and_stop_monitoring(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """Test removing a channel and stopping its monitoring."""
        mock_thread = MagicMock()
        multi_monitor.monitor_threads["channel-to-remove"] = mock_thread

        multi_monitor.remove_channel_and_stop_monitoring("channel-to-remove")

        assert "channel-to-remove" not in multi_monitor.monitor_threads
        mock_thread.stop.assert_called_once()

    def test_remove_channel_does_nothing_for_unknown_channel(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """Test that remove_channel_and_stop_monitoring does nothing for unknown channel."""
        # Should not raise an error
        multi_monitor.remove_channel_and_stop_monitoring("unknown-channel")

        assert len(multi_monitor.monitor_threads) == 0


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

    def test_handle_live_stream_exception_sends_download_failed_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """다운로드 예외 발생 시 notify_download_failed가 호출된다."""
        with patch.object(
            monitor_thread.downloader, "download", side_effect=Exception("ffmpeg crashed")
        ):
            with pytest.raises(Exception):
                monitor_thread._handle_live_stream(
                    "https://youtube.com/watch?v=abc", "방송 제목"
                )

        mock_notifier.notify_download_failed.assert_called_once_with(
            channel_name="Test Channel",
            error_message="ffmpeg crashed",
        )

    def test_monitor_loop_exception_sends_error_notification(
        self, monitor_thread: ChannelMonitorThread, mock_notifier: MagicMock
    ):
        """_monitor_cycle 예외 시 notify_error가 호출된다."""

        def cycle_side_effect():
            monitor_thread.is_running = False
            raise Exception("API timeout")

        with patch.object(monitor_thread, "_monitor_cycle", side_effect=cycle_side_effect):
            with patch("src.yt_monitor.multi_channel_monitor.time.sleep"):
                monitor_thread.is_running = True
                monitor_thread._monitor_loop()

        mock_notifier.notify_error.assert_called_once_with(
            channel_name="Test Channel",
            error_message="API timeout",
        )

    def test_monitor_loop_auth_error_sends_bot_detection_notification(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ):
        """YouTubeAuthError 발생 시 notify_bot_detection이 호출된다."""
        from src.yt_monitor.alert_cooldown import AlertCooldown

        thread = ChannelMonitorThread(
            channel=sample_channel,
            global_settings=global_settings,
            youtube_client=MagicMock(),
            notifier=mock_notifier,
            auth_alert_cooldown=AlertCooldown(cooldown_seconds=1800.0, clock=lambda: 1000.0),
        )

        def cycle_side_effect():
            thread.is_running = False
            raise YouTubeAuthError("Sign in to confirm you're not a bot")

        with patch.object(thread, "_monitor_cycle", side_effect=cycle_side_effect):
            with patch("src.yt_monitor.multi_channel_monitor.time.sleep"):
                thread.is_running = True
                thread._monitor_loop()

        mock_notifier.notify_bot_detection.assert_called_once_with(
            channel_name="Test Channel",
            detail="Sign in to confirm you're not a bot",
        )
        mock_notifier.notify_error.assert_not_called()

    def test_monitor_loop_auth_error_respects_cooldown(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ):
        """쿨다운 내 반복되는 YouTubeAuthError는 1번만 알림을 보낸다."""
        from src.yt_monitor.alert_cooldown import AlertCooldown

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
            with patch("src.yt_monitor.multi_channel_monitor.time.sleep"):
                thread.is_running = True
                thread._monitor_loop()

        assert mock_notifier.notify_bot_detection.call_count == 1

    def test_monitor_loop_auth_error_after_cooldown_sends_again(
        self,
        sample_channel: ChannelDTO,
        global_settings: GlobalSettingsDTO,
        mock_notifier: MagicMock,
        initialized_logger,
    ):
        """쿨다운 경과 후 재발생하면 다시 알림을 보낸다."""
        from src.yt_monitor.alert_cooldown import AlertCooldown

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
            with patch("src.yt_monitor.multi_channel_monitor.time.sleep"):
                thread.is_running = True
                thread._monitor_loop()

        assert mock_notifier.notify_bot_detection.call_count == 2


class TestMultiChannelMonitorBackgroundThread:
    """백그라운드 스레드에서 start() 호출 시 SIGTERM 등록을 건너뛰는지 검증.

    웹 라우트의 /api/monitor/start는 데몬 스레드 위에서 monitor.start()를
    호출한다. signal.signal()은 메인 스레드에서만 호출 가능하므로,
    백그라운드 스레드 진입 시 등록을 건너뛰어야 한다.
    """

    def test_start_in_background_thread_skips_signal_registration(
        self,
        tmp_path: Path,
        initialized_logger,
    ):
        """sub-thread에서 start() 호출 시 signal.signal()이 호출되지 않아야 한다."""
        import threading as real_threading

        manager = MagicMock(spec=ChannelManager)
        manager.list_channels.return_value = [
            ChannelDTO(
                id="ch1",
                name="Test Channel",
                url="https://www.youtube.com/@TestChannel",
            )
        ]
        manager.get_global_settings.return_value = GlobalSettingsDTO(
            download_directory=str(tmp_path / "downloads"),
            log_file=str(tmp_path / "test.log"),
        )

        mock_youtube_client = MagicMock()
        mock_youtube_client.check_if_live.return_value = (False, None)
        mock_notifier = MagicMock()

        monitor = MultiChannelMonitor(
            channel_manager=manager,
            youtube_client=mock_youtube_client,
            notifier=mock_notifier,
        )

        run_error: dict = {}

        def run_monitor():
            try:
                with patch("src.yt_monitor.multi_channel_monitor.signal") as mock_sig:
                    with patch("src.yt_monitor.multi_channel_monitor.time.sleep") as mock_sleep:
                        # 첫 sleep에서 즉시 종료 — 핸들러 등록 분기를 통과한 직후 빠진다
                        def stop_loop(*args, **kwargs):
                            monitor.is_running = False

                        mock_sleep.side_effect = stop_loop
                        monitor.start()
                        run_error["signal_called"] = mock_sig.signal.called
            except Exception as error:
                run_error["error"] = error

        worker = real_threading.Thread(target=run_monitor)
        worker.start()
        worker.join(timeout=5.0)

        assert "error" not in run_error, f"start() raised: {run_error.get('error')}"
        assert run_error.get("signal_called") is False, (
            "백그라운드 스레드에서는 signal.signal()이 호출되면 안 됨"
        )
        monitor.stop()


class TestMultiChannelMonitorSigterm:
    """SIGTERM 수신 시 notify_monitor_stopped가 호출되는지 검증."""

    @pytest.fixture
    def mock_channel_manager(self, tmp_path: Path) -> MagicMock:
        from src.yt_monitor.channel_manager import ChannelManager
        manager = MagicMock(spec=ChannelManager)
        manager.list_channels.return_value = [
            ChannelDTO(
                id="ch1",
                name="Test Channel",
                url="https://www.youtube.com/@TestChannel",
            )
        ]
        manager.get_global_settings.return_value = GlobalSettingsDTO(
            download_directory=str(tmp_path / "downloads"),
            log_file=str(tmp_path / "test.log"),
        )
        return manager

    def test_sigterm_sends_monitor_stopped_notification(
        self,
        mock_channel_manager: MagicMock,
        initialized_logger,
    ):
        """SIGTERM 수신 시 notify_monitor_stopped(reason='docker stop (SIGTERM)')가 호출된다."""
        import signal as real_signal

        mock_youtube_client = MagicMock()
        mock_youtube_client.check_if_live.return_value = (False, None)
        mock_notifier = MagicMock()

        monitor = MultiChannelMonitor(
            channel_manager=mock_channel_manager,
            youtube_client=mock_youtube_client,
            notifier=mock_notifier,
        )

        captured_handler = {}

        def capture_and_stop(sig, handler):
            """핸들러를 캡처하고 즉시 루프를 종료시킨다."""
            captured_handler[sig] = handler
            monitor.is_running = False  # while 루프 즉시 종료

        with patch("src.yt_monitor.multi_channel_monitor.signal") as mock_sig:
            mock_sig.SIGTERM = real_signal.SIGTERM
            mock_sig.signal.side_effect = capture_and_stop
            with patch("src.yt_monitor.multi_channel_monitor.time.sleep"):
                monitor.start()

        assert real_signal.SIGTERM in captured_handler

        captured_handler[real_signal.SIGTERM](real_signal.SIGTERM, None)
        mock_notifier.notify_monitor_stopped.assert_called_with(
            reason="docker stop (SIGTERM)"
        )
