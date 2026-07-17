"""Multi-channel monitoring service contracts."""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.channels.models import ChannelDTO, GlobalSettingsDTO
from src.yt_monitor.channels.repository import ChannelManager
from src.yt_monitor.monitoring.service import MultiChannelMonitor

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
        youtube_client = cast(MagicMock, multi_monitor.youtube_client)
        youtube_client.check_if_live.return_value = (False, None)

        def exit_keep_alive_loop(sig, handler):
            # SIGTERM 핸들러 등록 지점에서 메인 while 루프를 즉시 종료시킨다
            multi_monitor.is_running = False

        with patch("src.yt_monitor.monitoring.service.get_notifier"):
            with patch("src.yt_monitor.monitoring.service.signal") as mock_sig:
                mock_sig.signal.side_effect = exit_keep_alive_loop
                with patch("src.yt_monitor.monitoring.service.time") as mock_time:
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

    def test_sync_channel_monitors_starts_new_enabled_channel(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
        global_settings: GlobalSettingsDTO,
    ):
        """웹에서 추가된 enabled 채널이 실행 중인 monitor thread로 반영된다."""
        channel = ChannelDTO(
            id="new-channel",
            name="New Channel",
            url="https://www.youtube.com/@NewChannel",
        )
        mock_channel_manager.list_channels.return_value = [channel]
        mock_channel_manager.get_global_settings.return_value = global_settings
        new_thread = MagicMock()
        new_thread.channel = channel
        new_thread.global_settings = global_settings
        multi_monitor.is_running = True

        with patch.object(
            multi_monitor,
            "_build_channel_thread",
            return_value=new_thread,
        ):
            multi_monitor._sync_channel_monitors()

        assert multi_monitor.monitor_threads["new-channel"] is new_thread
        new_thread.start.assert_called_once()

    def test_sync_channel_monitors_stops_disabled_or_removed_channel(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
        global_settings: GlobalSettingsDTO,
    ):
        """channels.json에서 빠진 enabled 채널의 기존 thread를 중지한다."""
        old_channel = ChannelDTO(
            id="old-channel",
            name="Old Channel",
            url="https://www.youtube.com/@OldChannel",
        )
        old_thread = MagicMock()
        old_thread.channel = old_channel
        old_thread.global_settings = global_settings
        multi_monitor.monitor_threads["old-channel"] = old_thread
        multi_monitor.is_running = True
        mock_channel_manager.list_channels.return_value = []
        mock_channel_manager.get_global_settings.return_value = global_settings

        multi_monitor._sync_channel_monitors()

        assert "old-channel" not in multi_monitor.monitor_threads
        old_thread.stop.assert_called_once()

    def test_sync_channel_monitors_restarts_updated_channel(
        self,
        multi_monitor: MultiChannelMonitor,
        mock_channel_manager: MagicMock,
        global_settings: GlobalSettingsDTO,
    ):
        """URL/포맷 등 채널 설정 변경은 기존 thread 재시작으로 반영한다."""
        old_channel = ChannelDTO(
            id="channel",
            name="Channel",
            url="https://www.youtube.com/@OldChannel",
        )
        updated_channel = ChannelDTO(
            id="channel",
            name="Channel",
            url="https://www.youtube.com/@NewChannel",
        )
        old_thread = MagicMock()
        old_thread.channel = old_channel
        old_thread.global_settings = global_settings
        new_thread = MagicMock()
        new_thread.channel = updated_channel
        new_thread.global_settings = global_settings
        multi_monitor.monitor_threads["channel"] = old_thread
        multi_monitor.is_running = True
        mock_channel_manager.list_channels.return_value = [updated_channel]
        mock_channel_manager.get_global_settings.return_value = global_settings

        with patch.object(
            multi_monitor,
            "_build_channel_thread",
            return_value=new_thread,
        ):
            multi_monitor._sync_channel_monitors()

        assert multi_monitor.monitor_threads["channel"] is new_thread
        old_thread.stop.assert_called_once()
        new_thread.start.assert_called_once()

    def test_remove_waits_for_monitor_threads_lock(
        self,
        multi_monitor: MultiChannelMonitor,
    ):
        """FastAPI thread의 remove는 monitor_threads lock 해제 전 실행되면 안 된다."""
        import threading

        class ObservableLock:
            def __init__(self):
                self._lock = threading.RLock()
                self.enter_attempted = threading.Event()

            def __enter__(self):
                self.enter_attempted.set()
                self._lock.acquire()
                return self

            def __exit__(self, *_args):
                self._lock.release()

        channel_thread = MagicMock()
        multi_monitor.monitor_threads["channel"] = channel_thread
        finished = threading.Event()
        observable_lock = ObservableLock()
        setattr(multi_monitor, "_monitor_threads_lock", observable_lock)

        def remove_channel() -> None:
            multi_monitor.remove_channel_and_stop_monitoring("channel")
            finished.set()

        with observable_lock:
            observable_lock.enter_attempted.clear()
            worker = threading.Thread(target=remove_channel)
            worker.start()
            assert observable_lock.enter_attempted.wait(timeout=1.0)
            assert finished.is_set() is False

        worker.join(timeout=1.0)
        assert finished.is_set()
        assert "channel" not in multi_monitor.monitor_threads
        channel_thread.stop.assert_called_once()



class TestMultiChannelMonitorBackgroundThread:
    """백그라운드 스레드에서 start() 호출 시 SIGTERM 등록을 건너뛰는지 검증.

    현재 Compose 운영에서는 yt-monitor가 메인 스레드에서 실행되지만,
    라이브러리 사용자가 별도 스레드에서 monitor.start()를 호출해도
    signal.signal() 때문에 죽지 않아야 한다.
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
                with patch("src.yt_monitor.monitoring.service.signal") as mock_sig:
                    with patch("src.yt_monitor.monitoring.service.time.sleep") as mock_sleep:
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
        from src.yt_monitor.channels.repository import ChannelManager
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

        with patch("src.yt_monitor.monitoring.service.signal") as mock_sig:
            mock_sig.SIGTERM = real_signal.SIGTERM
            mock_sig.signal.side_effect = capture_and_stop
            with patch("src.yt_monitor.monitoring.service.time.sleep"):
                monitor.start()

        assert real_signal.SIGTERM in captured_handler

        captured_handler[real_signal.SIGTERM](real_signal.SIGTERM, None)
        mock_notifier.notify_monitor_stopped.assert_called_with(
            reason="docker stop (SIGTERM)"
        )
