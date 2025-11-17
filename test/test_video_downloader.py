"""Tests for VideoDownloader module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.video_downloader import VideoDownloader


class TestVideoDownloader:
    """Test cases for VideoDownloader class."""

    def test_init_creates_output_directory(self, tmp_path):
        """Test that __init__ creates the output directory."""
        output_dir = tmp_path / "test_downloads"
        downloader = VideoDownloader(output_dir=str(output_dir))

        assert output_dir.exists()
        assert downloader.output_dir == str(output_dir)
        assert downloader.quality == "best"
        assert downloader.audio_only is False

    def test_init_with_custom_settings(self, tmp_path):
        """Test initialization with custom settings."""
        output_dir = tmp_path / "custom"
        downloader = VideoDownloader(
            output_dir=str(output_dir), quality="720", audio_only=True
        )

        assert downloader.quality == "720"
        assert downloader.audio_only is True

    def test_get_format_string_audio_only(self):
        """Test format string generation for audio-only mode."""
        downloader = VideoDownloader(audio_only=True)
        format_str = downloader._get_format_string()

        assert format_str == "bestaudio/best"

    def test_get_format_string_best_quality(self):
        """Test format string for best quality."""
        downloader = VideoDownloader(quality="best")
        format_str = downloader._get_format_string()

        assert format_str == "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    def test_get_format_string_specific_quality(self):
        """Test format string for specific quality."""
        downloader = VideoDownloader(quality="720")
        format_str = downloader._get_format_string()

        assert format_str == "bestvideo[height<=720]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]"

    def test_build_ydl_options_video(self, tmp_path):
        """Test yt-dlp options building for video download."""
        downloader = VideoDownloader(output_dir=str(tmp_path), quality="1080")
        output_path = str(tmp_path / "test.mp4")

        opts = downloader._build_ydl_options(output_path)

        assert opts["format"] == "bestvideo[height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        assert opts["outtmpl"] == output_path
        assert opts["merge_output_format"] == "mp4"
        assert opts["prefer_ffmpeg"] is True
        assert opts["keepvideo"] is False
        assert "postprocessors" in opts
        assert opts["postprocessors"][0]["key"] == "FFmpegVideoConvertor"
        assert "postprocessor_args" in opts
        assert "-c:a" in opts["postprocessor_args"]["FFmpegVideoConvertor"]
        assert "aac" in opts["postprocessor_args"]["FFmpegVideoConvertor"]

    def test_build_ydl_options_audio(self, tmp_path):
        """Test yt-dlp options building for audio download."""
        downloader = VideoDownloader(output_dir=str(tmp_path), audio_only=True)
        output_path = str(tmp_path / "test.mp3")

        opts = downloader._build_ydl_options(output_path)

        assert opts["format"] == "bestaudio/best"
        assert "postprocessors" in opts
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

    @patch("src.yt_monitor.video_downloader.yt_dlp.YoutubeDL")
    def test_download_success_video(self, mock_ydl_class, tmp_path):
        """Test successful video download."""
        # Mock YoutubeDL
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Mock video info
        mock_ydl.extract_info.return_value = {
            "title": "Test Video",
            "duration": 125,  # 2분 5초
        }

        downloader = VideoDownloader(output_dir=str(tmp_path))
        success = downloader.download(
            url="https://youtube.com/watch?v=test123", filename="test_video"
        )

        assert success is True
        mock_ydl.download.assert_called_once()

    @patch("src.yt_monitor.video_downloader.yt_dlp.YoutubeDL")
    def test_download_success_audio(self, mock_ydl_class, tmp_path):
        """Test successful audio download."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        mock_ydl.extract_info.return_value = {
            "title": "Test Audio",
            "duration": 180,
        }

        downloader = VideoDownloader(output_dir=str(tmp_path), audio_only=True)
        success = downloader.download(
            url="https://youtube.com/watch?v=test123", filename="test_audio"
        )

        assert success is True

        # Check that audio extraction postprocessor is set
        call_args = mock_ydl_class.call_args
        opts = call_args[0][0]
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

    @patch("src.yt_monitor.video_downloader.yt_dlp.YoutubeDL")
    def test_download_auto_filename(self, mock_ydl_class, tmp_path):
        """Test download with auto-generated filename."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        mock_ydl.extract_info.return_value = {
            "title": "Test",
            "duration": 60,
        }

        downloader = VideoDownloader(output_dir=str(tmp_path))
        success = downloader.download(url="https://youtube.com/watch?v=test123")

        assert success is True
        # Verify that a timestamp-based filename was used
        call_args = mock_ydl_class.call_args
        opts = call_args[0][0]
        assert "video_" in opts["outtmpl"]

    @patch("src.yt_monitor.video_downloader.yt_dlp.YoutubeDL")
    def test_download_failure(self, mock_ydl_class, tmp_path):
        """Test download failure handling."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Simulate download error
        mock_ydl.extract_info.side_effect = Exception("Download failed")

        downloader = VideoDownloader(output_dir=str(tmp_path))
        success = downloader.download(url="https://youtube.com/watch?v=invalid")

        assert success is False

    @patch("src.yt_monitor.video_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info(self, mock_ydl_class):
        """Test getting video information without downloading."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        mock_info = {
            "title": "Test Video",
            "duration": 300,
            "uploader": "Test Channel",
            "view_count": 1000,
            "upload_date": "20240101",
            "description": "Test description",
            "formats": [
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "resolution": "1280x720",
                    "filesize": 10000000,
                }
            ],
        }
        mock_ydl.extract_info.return_value = mock_info

        downloader = VideoDownloader()
        info = downloader.get_video_info(url="https://youtube.com/watch?v=test123")

        assert info["title"] == "Test Video"
        assert info["duration"] == 300
        assert info["uploader"] == "Test Channel"
        assert len(info["formats"]) == 1

    def test_quality_choices(self, tmp_path):
        """Test various quality settings."""
        qualities = ["2160", "1440", "1080", "720", "480", "360", "best"]

        for quality in qualities:
            downloader = VideoDownloader(output_dir=str(tmp_path), quality=quality)
            format_str = downloader._get_format_string()

            if quality == "best":
                assert format_str == "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            else:
                assert f"height<={quality}" in format_str
                assert "ext=m4a" in format_str
