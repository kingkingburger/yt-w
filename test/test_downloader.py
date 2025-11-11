"""Tests for stream downloader module."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch, MagicMock

from src.yt_monitor.downloader import StreamDownloader
from src.yt_monitor.logger import Logger


class TestStreamDownloader:
    """Test StreamDownloader class."""

    @pytest.fixture(autouse=True)
    def setup_logger(self, tmp_path):
        """Setup logger for tests."""
        log_file = tmp_path / "test.log"
        Logger.initialize(str(log_file))
        yield
        Logger._initialized = False
        Logger._instance = None

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def downloader(self, temp_dir):
        """Create a StreamDownloader instance for testing."""
        return StreamDownloader(
            download_directory=temp_dir,
            download_format="best"
        )

    def test_initialization(self, temp_dir):
        """Test downloader initialization."""
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="bestvideo+bestaudio"
        )

        assert downloader.download_directory == temp_dir
        assert downloader.download_format == "bestvideo+bestaudio"
        assert downloader.logger is not None

    def test_initialization_creates_directory(self):
        """Test that initialization creates download directory."""
        with TemporaryDirectory() as tmpdir:
            download_dir = str(Path(tmpdir) / "nested" / "downloads")

            downloader = StreamDownloader(
                download_directory=download_dir,
                download_format="best"
            )

            assert Path(download_dir).exists()

    def test_build_ydl_options(self, downloader):
        output_file = "/path/to/output.mp4"
        options = downloader._build_ydl_options(output_file)

        assert options['format'] == "best"
        assert options['outtmpl'] == output_file
        assert options['live_from_start'] is True
        assert options['merge_output_format'] == 'mp4'
        assert 'postprocessors' in options

    @patch('src.yt_monitor.downloader.subprocess.run')
    @patch('src.yt_monitor.downloader.os.path.exists')
    @patch('src.yt_monitor.downloader.os.remove')
    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl_class, mock_remove, mock_exists, mock_subprocess, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.return_value = None
        mock_ydl_class.return_value = mock_ydl

        mock_exists.return_value = True
        mock_subprocess.return_value = Mock(returncode=0)

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="test_stream"
        )

        assert result is True
        mock_ydl.download.assert_called_once()
        mock_subprocess.assert_called_once()
        mock_remove.assert_called_once()

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_failure(self, mock_ydl_class, downloader):
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

    @patch('src.yt_monitor.downloader.subprocess.run')
    @patch('src.yt_monitor.downloader.os.path.exists')
    @patch('src.yt_monitor.downloader.os.remove')
    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_download_with_custom_prefix(self, mock_ydl_class, mock_remove, mock_exists, mock_subprocess, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.return_value = None
        mock_ydl_class.return_value = mock_ydl

        mock_exists.return_value = True
        mock_subprocess.return_value = Mock(returncode=0)

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="custom_prefix"
        )

        assert result is True
        call_args = mock_ydl_class.call_args
        ydl_opts = call_args[0][0]
        assert "custom_prefix" in ydl_opts['outtmpl']

    @patch('src.yt_monitor.downloader.yt_dlp.YoutubeDL')
    def test_perform_download(self, mock_ydl_class, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl_class.return_value = mock_ydl

        stream_url = "https://www.youtube.com/watch?v=test123"
        ydl_opts = {'format': 'best'}

        downloader._perform_download(stream_url, ydl_opts)

        mock_ydl.download.assert_called_once_with([stream_url])

    @patch('src.yt_monitor.downloader.subprocess.run')
    def test_split_video_success(self, mock_subprocess, downloader):
        mock_subprocess.return_value = Mock(returncode=0)

        downloader._split_video('input.mp4', 'output%03d.mp4')

        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert 'ffmpeg' in cmd
        assert '-segment_time' in cmd
        assert '1800' in cmd

    @patch('src.yt_monitor.downloader.subprocess.run')
    def test_split_video_failure(self, mock_subprocess, downloader):
        mock_subprocess.return_value = Mock(returncode=1, stderr="FFmpeg error")

        with pytest.raises(Exception, match="FFmpeg split failed"):
            downloader._split_video('input.mp4', 'output%03d.mp4')
