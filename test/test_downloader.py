"""Tests for stream downloader module."""

import logging
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch, MagicMock

from src.yt_monitor.downloader import StreamDownloader


class TestStreamDownloader:
    """Test StreamDownloader class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def downloader(self, temp_dir):
        """Create a StreamDownloader instance for testing."""
        logger = logging.getLogger("test")
        return StreamDownloader(
            download_directory=temp_dir,
            download_format="best",
            logger=logger
        )

    def test_initialization(self, temp_dir):
        """Test downloader initialization."""
        logger = logging.getLogger("test")
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="bestvideo+bestaudio",
            logger=logger
        )

        assert downloader.download_directory == temp_dir
        assert downloader.download_format == "bestvideo+bestaudio"
        assert downloader.logger == logger

    def test_initialization_creates_directory(self):
        """Test that initialization creates download directory."""
        with TemporaryDirectory() as tmpdir:
            download_dir = str(Path(tmpdir) / "nested" / "downloads")
            logger = logging.getLogger("test")

            downloader = StreamDownloader(
                download_directory=download_dir,
                download_format="best",
                logger=logger
            )

            assert Path(download_dir).exists()

    def test_generate_output_path(self, downloader):
        """Test output path generation."""
        output_path = downloader._generate_output_path("test_stream")

        assert "test_stream_" in output_path
        assert output_path.endswith(".%(ext)s")
        assert downloader.download_directory in output_path

    def test_build_ydl_options(self, downloader):
        """Test yt-dlp options building."""
        output_template = "/path/to/output.mp4"
        options = downloader._build_ydl_options(output_template)

        assert options['format'] == "best"
        assert options['outtmpl'] == output_template
        assert options['live_from_start'] is True
        assert options['merge_output_format'] == 'mp4'
        assert 'postprocessors' in options

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl_class, downloader):
        """Test successful download."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.return_value = None
        mock_ydl_class.return_value = mock_ydl

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="test_stream"
        )

        assert result is True
        mock_ydl.download.assert_called_once()

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_failure(self, mock_ydl_class, downloader):
        """Test download failure."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.side_effect = Exception("Download error")
        mock_ydl_class.return_value = mock_ydl

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="test_stream"
        )

        assert result is False

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_with_custom_prefix(self, mock_ydl_class, downloader):
        """Test download with custom filename prefix."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.return_value = None
        mock_ydl_class.return_value = mock_ydl

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="custom_prefix"
        )

        assert result is True

        # Verify the output template contains custom prefix
        call_args = mock_ydl_class.call_args
        ydl_opts = call_args[0][0]
        assert "custom_prefix" in ydl_opts['outtmpl']

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_perform_download(self, mock_ydl_class, downloader):
        """Test _perform_download method."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl_class.return_value = mock_ydl

        stream_url = "https://www.youtube.com/watch?v=test123"
        ydl_opts = {'format': 'best'}

        downloader._perform_download(stream_url, ydl_opts)

        mock_ydl.download.assert_called_once_with([stream_url])
