"""Tests for multi_channel_monitor module."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.channel_manager import ChannelDTO, GlobalSettingsDTO, ChannelManager
from src.yt_monitor.multi_channel_monitor import (
    ChannelMonitorThread,
    MultiChannelMonitor,
)
from src.yt_monitor.youtube_client import LiveStreamInfo


class TestChannelMonitorThread:
    """Test cases for ChannelMonitorThread class."""

    @pytest.fixture
    def sample_channel(self) -> ChannelDTO:
        """Create sample channel for testing."""
        return ChannelDTO(
            id="test-channel-id",
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
            enabled=True,
        )

    @pytest.fixture
    def global_settings(self, temp_dir: Path) -> GlobalSettingsDTO:
        """Create global settings for testing."""
        return GlobalSettingsDTO(
            check_interval_seconds=1,
            download_directory=str(temp_dir / "downloads"),
            log_file=str(temp_dir / "test.log"),
            split_mode="time",
            split_time_minutes=30,
        )

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

        expected_dir = temp_dir / "downloads" / "Test Channel"
        assert expected_dir.exists()

    def test_sanitize_name_removes_invalid_chars(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that _sanitize_name removes invalid filesystem characters."""
        invalid_name = 'Test<>:"/\\|?*Channel'

        sanitized = monitor_thread._sanitize_name(invalid_name)

        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert '"' not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized

    def test_sanitize_name_preserves_valid_chars(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that _sanitize_name preserves valid characters."""
        valid_name = "Test Channel 123"

        sanitized = monitor_thread._sanitize_name(valid_name)

        assert sanitized == "Test Channel 123"

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

    def test_handle_live_stream_sets_is_downloading(
        self, monitor_thread: ChannelMonitorThread
    ):
        """Test that _handle_live_stream sets is_downloading flag."""
        with patch.object(monitor_thread.downloader, "download", return_value=True):
            monitor_thread._handle_live_stream(
                "https://www.youtube.com/watch?v=test",
                "Test Stream",
            )

        assert monitor_thread.is_downloading is False  # Reset after download

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
        with patch(
            "src.yt_monitor.multi_channel_monitor.ChannelManager"
        ) as mock_manager:
            with patch(
                "src.yt_monitor.multi_channel_monitor.YouTubeClient"
            ) as mock_client:
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
        """Test that start() creates monitor threads for each channel."""
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

        # Run start in a separate thread to avoid blocking
        def start_and_stop():
            multi_monitor.is_running = True
            # Just set up threads, don't actually loop
            global_settings = mock_channel_manager.get_global_settings()
            for channel in channels:
                from src.yt_monitor.multi_channel_monitor import ChannelMonitorThread

                monitor_thread = ChannelMonitorThread(
                    channel=channel,
                    global_settings=global_settings,
                    youtube_client=multi_monitor.youtube_client,
                )
                multi_monitor.monitor_threads[channel.id] = monitor_thread

        start_and_stop()

        assert len(multi_monitor.monitor_threads) == 2
        assert "channel1" in multi_monitor.monitor_threads
        assert "channel2" in multi_monitor.monitor_threads

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
