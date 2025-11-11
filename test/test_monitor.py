"""Tests for live stream monitor module."""

import logging
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.yt_monitor.config import Config
from src.yt_monitor.monitor import LiveStreamMonitor
from src.yt_monitor.youtube_client import LiveStreamInfo


class TestLiveStreamMonitor:
    """Test LiveStreamMonitor class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return Config(
            channel_url="https://www.youtube.com/@test",
            check_interval_seconds=1,
            download_directory="./test_downloads",
            log_file="./test.log",
            video_quality="best",
            download_format="best"
        )

    @pytest.fixture
    def logger(self):
        """Create a test logger."""
        return logging.getLogger("test")

    @pytest.fixture
    def mock_youtube_client(self):
        """Create a mock YouTubeClient."""
        return Mock()

    @pytest.fixture
    def mock_downloader(self):
        """Create a mock StreamDownloader."""
        return Mock()

    @pytest.fixture
    def monitor(self, config, logger, mock_youtube_client, mock_downloader):
        """Create a LiveStreamMonitor instance for testing."""
        return LiveStreamMonitor(
            config=config,
            logger=logger,
            youtube_client=mock_youtube_client,
            downloader=mock_downloader
        )

    def test_initialization(self, config, logger):
        """Test monitor initialization."""
        monitor = LiveStreamMonitor(config=config, logger=logger)

        assert monitor.config == config
        assert monitor.logger == logger
        assert monitor.youtube_client is not None
        assert monitor.downloader is not None
        assert monitor.is_downloading is False

    def test_initialization_with_custom_clients(
        self, config, logger, mock_youtube_client, mock_downloader
    ):
        """Test monitor initialization with custom clients."""
        monitor = LiveStreamMonitor(
            config=config,
            logger=logger,
            youtube_client=mock_youtube_client,
            downloader=mock_downloader
        )

        assert monitor.youtube_client == mock_youtube_client
        assert monitor.downloader == mock_downloader

    @patch('src.yt_monitor.monitor.time.sleep')
    def test_monitor_cycle_no_live_stream(
        self, mock_sleep, monitor, mock_youtube_client
    ):
        """Test monitor cycle when no live stream is found."""
        mock_youtube_client.check_if_live.return_value = (False, None)

        monitor._monitor_cycle()

        mock_youtube_client.check_if_live.assert_called_once()
        mock_sleep.assert_called_once()
        assert monitor.is_downloading is False

    @patch('src.yt_monitor.monitor.time.sleep')
    def test_monitor_cycle_live_stream_found(
        self, mock_sleep, monitor, mock_youtube_client, mock_downloader
    ):
        """Test monitor cycle when live stream is found."""
        stream_info = LiveStreamInfo(
            video_id="test123",
            url="https://www.youtube.com/watch?v=test123"
        )
        mock_youtube_client.check_if_live.return_value = (True, stream_info)
        mock_downloader.download.return_value = True

        monitor._monitor_cycle()

        mock_youtube_client.check_if_live.assert_called_once()
        mock_downloader.download.assert_called_once_with(
            stream_url=stream_info.url,
            filename_prefix="침착맨_라이브"
        )
        assert monitor.is_downloading is False

    @patch('src.yt_monitor.monitor.time.sleep')
    def test_monitor_cycle_skips_when_downloading(
        self, mock_sleep, monitor, mock_youtube_client
    ):
        """Test that monitor cycle is skipped when already downloading."""
        monitor.is_downloading = True

        monitor._monitor_cycle()

        mock_youtube_client.check_if_live.assert_not_called()
        mock_sleep.assert_called_once()

    def test_handle_live_stream_successful_download(
        self, monitor, mock_downloader
    ):
        """Test handling live stream with successful download."""
        stream_url = "https://www.youtube.com/watch?v=test123"
        mock_downloader.download.return_value = True

        monitor._handle_live_stream(stream_url)

        mock_downloader.download.assert_called_once_with(
            stream_url=stream_url,
            filename_prefix="침착맨_라이브"
        )
        assert monitor.is_downloading is False

    def test_handle_live_stream_failed_download(
        self, monitor, mock_downloader
    ):
        """Test handling live stream with failed download."""
        stream_url = "https://www.youtube.com/watch?v=test123"
        mock_downloader.download.return_value = False

        monitor._handle_live_stream(stream_url)

        mock_downloader.download.assert_called_once()
        assert monitor.is_downloading is False

    def test_handle_live_stream_exception_resets_flag(
        self, monitor, mock_downloader
    ):
        """Test that is_downloading flag is reset even on exception."""
        stream_url = "https://www.youtube.com/watch?v=test123"
        mock_downloader.download.side_effect = Exception("Download error")

        with pytest.raises(Exception):
            monitor._handle_live_stream(stream_url)

        assert monitor.is_downloading is False

    @patch('src.yt_monitor.monitor.time.sleep')
    def test_start_with_keyboard_interrupt(
        self, mock_sleep, monitor, mock_youtube_client
    ):
        """Test that monitor stops gracefully on KeyboardInterrupt."""
        mock_youtube_client.check_if_live.return_value = (False, None)
        mock_sleep.side_effect = [None, KeyboardInterrupt()]

        monitor.start()

        # Should exit gracefully without raising exception
        assert True

    @patch('src.yt_monitor.monitor.time.sleep')
    def test_start_handles_exception(
        self, mock_sleep, monitor, mock_youtube_client
    ):
        """Test that monitor handles exceptions and continues."""
        mock_youtube_client.check_if_live.side_effect = [
            Exception("Network error"),
            KeyboardInterrupt()
        ]

        monitor.start()

        # Should handle exception and continue until KeyboardInterrupt
        assert mock_youtube_client.check_if_live.call_count == 2

    def test_log_startup_info(self, monitor, config):
        """Test that startup information is logged."""
        with patch.object(monitor.logger, 'info') as mock_info:
            monitor._log_startup_info()

            assert mock_info.call_count >= 3
            # Verify that important info is logged
            calls = [str(call) for call in mock_info.call_args_list]
            assert any(config.channel_url in str(call) for call in calls)
