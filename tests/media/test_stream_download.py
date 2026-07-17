"""Tests for stream_downloader module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.media.stream_download import StreamDownloader


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

    def test_build_ydl_options_preserves_live_download_contract(
        self, stream_downloader: StreamDownloader
    ):
        """yt-dlp 옵션은 라이브 대기와 MP4 후처리 계약을 함께 보존한다."""
        opts = stream_downloader._build_ydl_options("/path/to/output.mp4")

        assert opts["format"] == "bestvideo+bestaudio/best"
        assert opts["outtmpl"] == "/path/to/output.mp4"
        assert opts["live_from_start"] is False
        assert opts["merge_output_format"] == "mp4"
        assert opts["wait_for_video"] == (5, 20)
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
                "url": "https://direct-url.com/stream",
                "http_headers": {"User-Agent": "Mozilla/5.0"},
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.communicate.return_value = ("", "")
                mock_proc.returncode = 0
                mock_popen.return_value = mock_proc

                stream_downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test123",
                    "/output/pattern_%03d.mp4",
                )

                # Verify ffmpeg was called with correct segment time (10 * 60 = 600)
                call_args = mock_popen.call_args[0][0]
                segment_time_idx = call_args.index("-segment_time")
                assert call_args[segment_time_idx + 1] == "600"
                header_idx = call_args.index("-headers")
                input_idx = call_args.index("-i")
                assert header_idx < input_idx

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

            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.communicate.return_value = ("", "ffmpeg error detail")
                mock_proc.returncode = 1
                mock_popen.return_value = mock_proc

                with pytest.raises(Exception, match="FFmpeg segmented download failed"):
                    stream_downloader._download_with_realtime_split(
                        "https://www.youtube.com/watch?v=test123",
                        "/output/pattern_%03d.mp4",
                    )

    def test_stop_terminates_running_ffmpeg(self, stream_downloader: StreamDownloader):
        """stop()은 진행 중인 ffmpeg에 terminate 후 wait를 호출한다."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 살아 있음
        stream_downloader._proc = mock_proc

        stream_downloader.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    def test_stop_kills_when_terminate_times_out(
        self, stream_downloader: StreamDownloader
    ):
        """terminate가 timeout이면 kill로 강제 종료한다."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5),
            None,
        ]
        stream_downloader._proc = mock_proc

        stream_downloader.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    def test_stop_no_op_when_proc_already_finished(
        self, stream_downloader: StreamDownloader
    ):
        """proc.poll()이 None이 아니면(=종료됨) terminate를 호출하지 않는다."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        stream_downloader._proc = mock_proc

        stream_downloader.stop()

        mock_proc.terminate.assert_not_called()

    def test_stop_no_op_when_no_proc(self, stream_downloader: StreamDownloader):
        """진행 중인 다운로드가 없으면 stop()은 조용히 통과한다."""
        stream_downloader.stop()  # raise 없이 끝나야 한다

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
