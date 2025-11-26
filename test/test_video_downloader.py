"""Tests for video_downloader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.yt_monitor.video_downloader import VideoDownloader


class TestVideoDownloader:
    """Test cases for VideoDownloader class."""

    def test_init_creates_output_directory(self, temp_dir: Path):
        """Test that __init__ creates the output directory."""
        output_dir = temp_dir / "downloads"

        VideoDownloader(output_dir=str(output_dir))

        assert output_dir.exists()

    def test_init_default_values(self, temp_dir: Path):
        """Test VideoDownloader default values."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        assert downloader.quality == "best"
        assert downloader.audio_only is False

    def test_init_custom_values(self, temp_dir: Path):
        """Test VideoDownloader with custom values."""
        downloader = VideoDownloader(
            output_dir=str(temp_dir),
            quality="720",
            audio_only=True,
        )

        assert downloader.quality == "720"
        assert downloader.audio_only is True

    def test_get_format_string_audio_only(self, temp_dir: Path):
        """Test _get_format_string for audio only mode."""
        downloader = VideoDownloader(output_dir=str(temp_dir), audio_only=True)

        format_string = downloader._get_format_string()

        assert format_string == "bestaudio/best"

    def test_get_format_string_best_quality(self, temp_dir: Path):
        """Test _get_format_string for best quality."""
        downloader = VideoDownloader(output_dir=str(temp_dir), quality="best")

        format_string = downloader._get_format_string()

        assert "bestvideo" in format_string
        assert "bestaudio" in format_string

    def test_get_format_string_specific_quality(self, temp_dir: Path):
        """Test _get_format_string for specific quality."""
        downloader = VideoDownloader(output_dir=str(temp_dir), quality="720")

        format_string = downloader._get_format_string()

        assert "height<=720" in format_string

    def test_build_ydl_options_video(self, temp_dir: Path):
        """Test _build_ydl_options for video download."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        opts = downloader._build_ydl_options("/path/to/output.mp4")

        assert opts["outtmpl"] == "/path/to/output.mp4"
        assert opts["merge_output_format"] == "mp4"
        assert "postprocessors" in opts

    def test_build_ydl_options_audio(self, temp_dir: Path):
        """Test _build_ydl_options for audio download."""
        downloader = VideoDownloader(output_dir=str(temp_dir), audio_only=True)

        opts = downloader._build_ydl_options("/path/to/output.mp3")

        assert opts["format"] == "bestaudio/best"
        assert "postprocessors" in opts
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

    def test_build_ydl_options_has_performance_settings(self, temp_dir: Path):
        """Test that _build_ydl_options includes performance settings."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        opts = downloader._build_ydl_options("/path/to/output.mp4")

        assert opts["concurrent_fragment_downloads"] == 8
        assert opts["retries"] == 10

    def test_download_success(self, temp_dir: Path):
        """Test successful download."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "title": "Test Video",
                "duration": 120,
            }
            mock_ydl.return_value = mock_instance

            result = downloader.download("https://www.youtube.com/watch?v=test123")

            assert result is True
            mock_instance.download.assert_called_once()

    def test_download_failure(self, temp_dir: Path):
        """Test download failure."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.side_effect = Exception("Download failed")
            mock_ydl.return_value = mock_instance

            result = downloader.download("https://www.youtube.com/watch?v=test123")

            assert result is False

    def test_download_with_custom_filename(self, temp_dir: Path):
        """Test download with custom filename."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "title": "Test Video",
                "duration": 120,
            }
            mock_ydl.return_value = mock_instance

            result = downloader.download(
                "https://www.youtube.com/watch?v=test123",
                filename="custom_name",
            )

            assert result is True
            # Verify the custom filename was used in options
            call_args = mock_ydl.call_args
            opts = call_args[0][0]
            assert "custom_name" in opts["outtmpl"]

    def test_download_audio_only_uses_mp3_extension(self, temp_dir: Path):
        """Test that audio only download uses .mp3 extension."""
        downloader = VideoDownloader(output_dir=str(temp_dir), audio_only=True)

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "title": "Test Video",
                "duration": 120,
            }
            mock_ydl.return_value = mock_instance

            downloader.download("https://www.youtube.com/watch?v=test123")

            call_args = mock_ydl.call_args
            opts = call_args[0][0]
            assert opts["outtmpl"].endswith(".mp3")

    def test_get_video_info(self, temp_dir: Path):
        """Test get_video_info returns correct information."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "uploader": "Test Channel",
                "view_count": 1000,
                "upload_date": "20240101",
                "description": "Test description",
                "thumbnail": "https://example.com/thumb.jpg",
                "formats": [
                    {
                        "format_id": "22",
                        "ext": "mp4",
                        "resolution": "720p",
                        "filesize": 1000000,
                    }
                ],
            }
            mock_ydl.return_value = mock_instance

            info = downloader.get_video_info("https://www.youtube.com/watch?v=test123")

            assert info["title"] == "Test Video"
            assert info["duration"] == 300
            assert info["uploader"] == "Test Channel"
            assert info["view_count"] == 1000
            assert len(info["formats"]) == 1

    def test_get_video_info_skip_download(self, temp_dir: Path):
        """Test that get_video_info doesn't download the video."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "title": "Test",
                "formats": [],
            }
            mock_ydl.return_value = mock_instance

            downloader.get_video_info("https://www.youtube.com/watch?v=test123")

            # Verify extract_info was called with download=False
            mock_instance.extract_info.assert_called_once_with(
                "https://www.youtube.com/watch?v=test123", download=False
            )
