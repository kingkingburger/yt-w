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
            download_format="best",
            split_mode="time",
            split_time_minutes=30,
            split_size_mb=500,
        )

    def test_initialization(self, temp_dir):
        """Test downloader initialization."""
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="bestvideo+bestaudio",
            split_mode="size",
            split_time_minutes=15,
            split_size_mb=300,
        )

        assert downloader.download_directory == temp_dir
        assert downloader.download_format == "bestvideo+bestaudio"
        assert downloader.split_mode == "size"
        assert downloader.split_time_minutes == 15
        assert downloader.split_size_mb == 300
        assert downloader.logger is not None

    def test_initialization_creates_directory(self):
        """Test that initialization creates download directory."""
        with TemporaryDirectory() as tmpdir:
            download_dir = str(Path(tmpdir) / "nested" / "downloads")

            StreamDownloader(download_directory=download_dir, download_format="best")

            assert Path(download_dir).exists()

    def test_build_ydl_options(self, downloader):
        output_file = "/path/to/output.mp4"
        options = downloader._build_ydl_options(output_file)

        assert options["format"] == "best"
        assert options["outtmpl"] == output_file
        assert options["live_from_start"] is True
        assert options["merge_output_format"] == "mp4"
        assert "postprocessors" in options

    @patch("src.yt_monitor.downloader.subprocess.run")
    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_download_success(self, mock_ydl_class, mock_subprocess, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "url": "https://direct.stream.url/video.m3u8"
        }
        mock_ydl_class.return_value = mock_ydl

        mock_subprocess.return_value = Mock(returncode=0)

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="test_stream",
        )

        assert result is True
        mock_ydl.extract_info.assert_called_once()
        mock_subprocess.assert_called_once()

    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_download_failure(self, mock_ydl_class, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("Download error")
        mock_ydl_class.return_value = mock_ydl

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="test_stream",
        )

        assert result is False

    @patch("src.yt_monitor.downloader.subprocess.run")
    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_download_with_custom_prefix(
        self, mock_ydl_class, mock_subprocess, downloader
    ):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "url": "https://direct.stream.url/video.m3u8"
        }
        mock_ydl_class.return_value = mock_ydl

        mock_subprocess.return_value = Mock(returncode=0)

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123",
            filename_prefix="custom_prefix",
        )

        assert result is True
        cmd = mock_subprocess.call_args[0][0]
        output_pattern = cmd[-1]
        assert "custom_prefix" in output_pattern

    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_perform_download(self, mock_ydl_class, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl_class.return_value = mock_ydl

        stream_url = "https://www.youtube.com/watch?v=test123"
        ydl_opts = {"format": "best"}

        downloader._perform_download(stream_url, ydl_opts)

        mock_ydl.download.assert_called_once_with([stream_url])

    @patch("src.yt_monitor.downloader.subprocess.run")
    def test_split_video_by_time(self, mock_subprocess, temp_dir):
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="best",
            split_mode="time",
            split_time_minutes=15,
        )
        mock_subprocess.return_value = Mock(returncode=0)

        downloader._split_video("input.mp4", "output%03d.mp4")

        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-segment_time" in cmd
        assert "900" in cmd

    @patch("src.yt_monitor.downloader.subprocess.run")
    def test_split_video_by_size(self, mock_subprocess, temp_dir):
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="best",
            split_mode="size",
            split_size_mb=300,
        )
        mock_subprocess.return_value = Mock(returncode=0)

        downloader._split_video("input.mp4", "output%03d.mp4")

        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-segment_size" in cmd
        assert str(300 * 1024 * 1024) in cmd

    @patch("src.yt_monitor.downloader.subprocess.run")
    def test_split_video_failure(self, mock_subprocess, downloader):
        mock_subprocess.return_value = Mock(returncode=1, stderr="FFmpeg error")

        with pytest.raises(Exception, match="FFmpeg split failed"):
            downloader._split_video("input.mp4", "output%03d.mp4")

    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_download_without_split(self, mock_ydl_class, temp_dir):
        downloader = StreamDownloader(
            download_directory=temp_dir, download_format="best", split_mode="none"
        )

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.download.return_value = None
        mock_ydl_class.return_value = mock_ydl

        result = downloader.download(
            stream_url="https://www.youtube.com/watch?v=test123", filename_prefix="test"
        )

        assert result is True
        mock_ydl.download.assert_called_once()

    @patch("src.yt_monitor.downloader.yt_dlp.YoutubeDL")
    def test_get_direct_stream_url(self, mock_ydl_class, downloader):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "url": "https://direct.stream.url/video.m3u8"
        }
        mock_ydl_class.return_value = mock_ydl

        stream_url = "https://www.youtube.com/watch?v=test123"
        direct_url = downloader._get_direct_stream_url(stream_url)

        assert direct_url == "https://direct.stream.url/video.m3u8"
        mock_ydl.extract_info.assert_called_once_with(stream_url, download=False)

    @patch("src.yt_monitor.downloader.subprocess.run")
    @patch("src.yt_monitor.downloader.StreamDownloader._get_direct_stream_url")
    def test_download_with_realtime_split_time_mode(
        self, mock_get_url, mock_subprocess, temp_dir
    ):
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="best",
            split_mode="time",
            split_time_minutes=15,
        )
        mock_get_url.return_value = "https://direct.stream.url/video.m3u8"
        mock_subprocess.return_value = Mock(returncode=0)

        downloader._download_with_realtime_split(
            "https://www.youtube.com/watch?v=test123", "output%03d.mp4"
        )

        mock_get_url.assert_called_once()
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-segment_time" in cmd
        assert "900" in cmd

    @patch("src.yt_monitor.downloader.subprocess.run")
    @patch("src.yt_monitor.downloader.StreamDownloader._get_direct_stream_url")
    def test_download_with_realtime_split_size_mode(
        self, mock_get_url, mock_subprocess, temp_dir
    ):
        downloader = StreamDownloader(
            download_directory=temp_dir,
            download_format="best",
            split_mode="size",
            split_size_mb=100,
        )
        mock_get_url.return_value = "https://direct.stream.url/video.m3u8"
        mock_subprocess.return_value = Mock(returncode=0)

        downloader._download_with_realtime_split(
            "https://www.youtube.com/watch?v=test123", "output%03d.mp4"
        )

        mock_get_url.assert_called_once()
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-segment_size" in cmd
        assert str(100 * 1024 * 1024) in cmd

    @patch("src.yt_monitor.downloader.subprocess.run")
    @patch("src.yt_monitor.downloader.StreamDownloader._get_direct_stream_url")
    def test_download_with_realtime_split_failure(
        self, mock_get_url, mock_subprocess, downloader
    ):
        mock_get_url.return_value = "https://direct.stream.url/video.m3u8"
        mock_subprocess.return_value = Mock(returncode=1)

        with pytest.raises(Exception, match="FFmpeg download failed"):
            downloader._download_with_realtime_split(
                "https://www.youtube.com/watch?v=test123", "output%03d.mp4"
            )
