"""Tests for stream_downloader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.stream_downloader import StreamDownloader


class TestStreamDownloader:
    """Test cases for StreamDownloader class."""

    @pytest.fixture
    def stream_downloader(self, temp_dir: Path, initialized_logger) -> StreamDownloader:
        """Create StreamDownloader instance for testing."""
        return StreamDownloader(
            download_directory=str(temp_dir / "downloads"),
            download_format="bestvideo+bestaudio/best",
            split_mode="time",
            split_time_minutes=30,
            split_size_mb=500,
        )

    def test_init_creates_download_directory(self, temp_dir: Path, initialized_logger):
        """Test that __init__ creates the download directory."""
        download_dir = temp_dir / "new_downloads"

        StreamDownloader(
            download_directory=str(download_dir),
            download_format="bestvideo+bestaudio/best",
        )

        assert download_dir.exists()

    def test_init_default_split_values(self, temp_dir: Path, initialized_logger):
        """Test StreamDownloader default split values."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
        )

        assert downloader.split_mode == "time"
        assert downloader.split_time_minutes == 30
        assert downloader.split_size_mb == 500

    def test_init_custom_split_values(self, temp_dir: Path, initialized_logger):
        """Test StreamDownloader with custom split values."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
            split_mode="size",
            split_time_minutes=60,
            split_size_mb=1000,
        )

        assert downloader.split_mode == "size"
        assert downloader.split_time_minutes == 60
        assert downloader.split_size_mb == 1000

    def test_build_ydl_options(self, stream_downloader: StreamDownloader):
        """Test _build_ydl_options returns correct options."""
        opts = stream_downloader._build_ydl_options("/path/to/output.mp4")

        assert opts["format"] == "bestvideo+bestaudio/best"
        assert opts["outtmpl"] == "/path/to/output.mp4"
        assert opts["live_from_start"] is False
        assert opts["merge_output_format"] == "mp4"

    def test_build_ydl_options_includes_wait_for_video(
        self, stream_downloader: StreamDownloader
    ):
        """Test that _build_ydl_options includes wait_for_video setting."""
        opts = stream_downloader._build_ydl_options("/path/to/output.mp4")

        assert "wait_for_video" in opts
        assert opts["wait_for_video"] == (5, 20)

    def test_build_ydl_options_includes_postprocessors(
        self, stream_downloader: StreamDownloader
    ):
        """Test that _build_ydl_options includes postprocessors."""
        opts = stream_downloader._build_ydl_options("/path/to/output.mp4")

        assert "postprocessors" in opts
        assert len(opts["postprocessors"]) > 0
        assert opts["postprocessors"][0]["key"] == "FFmpegVideoConvertor"

    def test_download_no_split_mode(self, temp_dir: Path, initialized_logger):
        """Test download with split_mode='none'."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
            split_mode="none",
        )

        with patch.object(downloader, "_perform_download") as mock_download:
            result = downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename_prefix="test",
            )

            assert result is True
            mock_download.assert_called_once()

    def test_download_time_split_mode(self, stream_downloader: StreamDownloader):
        """Test download with split_mode='time'."""
        with patch.object(
            stream_downloader, "_download_with_realtime_split"
        ) as mock_split:
            result = stream_downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename_prefix="test",
            )

            assert result is True
            mock_split.assert_called_once()

    def test_download_size_split_mode(self, temp_dir: Path, initialized_logger):
        """Test download with split_mode='size'."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
            split_mode="size",
            split_size_mb=100,
        )

        with patch.object(downloader, "_download_with_realtime_split") as mock_split:
            result = downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename_prefix="test",
            )

            assert result is True
            mock_split.assert_called_once()

    def test_download_failure_returns_false(self, stream_downloader: StreamDownloader):
        """Test that download returns False on failure."""
        with patch.object(
            stream_downloader,
            "_download_with_realtime_split",
            side_effect=Exception("Download failed"),
        ):
            result = stream_downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename_prefix="test",
            )

            assert result is False

    def test_download_generates_timestamp_filename(
        self, stream_downloader: StreamDownloader
    ):
        """Test that download generates filename with timestamp."""
        with patch.object(
            stream_downloader, "_download_with_realtime_split"
        ) as mock_split:
            stream_downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename_prefix="mystream",
            )

            # Get the output pattern passed to the split function
            call_args = mock_split.call_args[0]
            output_pattern = call_args[1]

            assert "mystream" in output_pattern
            assert "part%03d.mp4" in output_pattern

    def test_download_with_realtime_split_time_mode(
        self, stream_downloader: StreamDownloader
    ):
        """Test _download_with_realtime_split calculates correct split time."""
        stream_downloader.split_mode = "time"
        stream_downloader.split_time_minutes = 10

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "url": "https://direct-url.com/stream"
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                stream_downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test123",
                    "/output/pattern_%03d.mp4",
                )

                # Verify ffmpeg was called with correct segment time (10 * 60 = 600)
                call_args = mock_run.call_args[0][0]
                segment_time_idx = call_args.index("-segment_time")
                assert call_args[segment_time_idx + 1] == "600"

    def test_download_with_realtime_split_size_mode(
        self, temp_dir: Path, initialized_logger
    ):
        """Test _download_with_realtime_split calculates time from size."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
            split_mode="size",
            split_size_mb=100,
        )

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "url": "https://direct-url.com/stream"
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test123",
                    "/output/pattern_%03d.mp4",
                )

                # Verify ffmpeg was called
                mock_run.assert_called_once()

    def test_download_with_realtime_split_dual_stream(
        self, stream_downloader: StreamDownloader
    ):
        """Test _download_with_realtime_split handles video+audio streams."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "requested_formats": [
                    {"url": "https://video-url.com"},
                    {"url": "https://audio-url.com"},
                ]
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                stream_downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test123",
                    "/output/pattern_%03d.mp4",
                )

                # Verify ffmpeg was called with two inputs
                call_args = mock_run.call_args[0][0]
                input_count = call_args.count("-i")
                assert input_count == 2

    def test_download_with_realtime_split_invalid_mode(
        self, temp_dir: Path, initialized_logger
    ):
        """Test _download_with_realtime_split raises error for invalid mode."""
        downloader = StreamDownloader(
            download_directory=str(temp_dir),
            download_format="bestvideo+bestaudio/best",
        )
        downloader.split_mode = "invalid"

        with pytest.raises(ValueError, match="Invalid split_mode"):
            downloader._download_with_realtime_split(
                "https://www.youtube.com/watch?v=test123",
                "/output/pattern_%03d.mp4",
            )

    def test_download_with_realtime_split_ffmpeg_failure(
        self, stream_downloader: StreamDownloader
    ):
        """Test _download_with_realtime_split raises on ffmpeg failure."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "url": "https://direct-url.com/stream"
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)

                with pytest.raises(Exception, match="FFmpeg segmented download failed"):
                    stream_downloader._download_with_realtime_split(
                        "https://www.youtube.com/watch?v=test123",
                        "/output/pattern_%03d.mp4",
                    )

    def test_perform_download(self, stream_downloader: StreamDownloader):
        """Test _perform_download calls yt-dlp correctly."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_ydl.return_value = mock_instance

            stream_downloader._perform_download(
                "https://www.youtube.com/watch?v=test123",
                {"format": "best"},
            )

            mock_instance.download.assert_called_once_with(
                ["https://www.youtube.com/watch?v=test123"]
            )
