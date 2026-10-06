"""Tests for video_downloader module."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
from yt_dlp import YoutubeDL

from src.yt_monitor.media.video_download import VideoDownloader


class TestVideoDownloader:
    """Test cases for VideoDownloader class."""

    def test_download_fragments_without_forced_range_headers(self, temp_dir: Path):
        """Exercise the real DASH downloader against a Range-rejecting server."""
        ranges = []
        payload = b"video-fragment"

        class FragmentHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                ranges.append(self.headers.get("Range"))
                if self.headers.get("Range"):
                    self.send_response(416)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), FragmentHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = temp_dir / "fragments.mp4"
        try:
            with patch(
                "src.yt_monitor.media.video_download.get_cookie_options",
                return_value={},
            ):
                opts = VideoDownloader(output_dir=str(temp_dir))._build_ydl_options(
                    str(output)
                )
            opts.update(
                quiet=True,
                retries=0,
                fragment_retries=0,
                skip_unavailable_fragments=False,
            )
            url = f"http://127.0.0.1:{server.server_port}/fragment"
            with YoutubeDL(opts) as ydl:
                success, _ = ydl.dl(
                    str(output),
                    {
                        "url": url,
                        "ext": "mp4",
                        "protocol": "http_dash_segments",
                        "fragments": [{"url": url}, {"url": url}],
                    },
                )
            assert success
            assert output.read_bytes() == payload * 2
            assert ranges == [None, None]
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    @pytest.mark.parametrize("separate_streams", [True, False])
    def test_get_video_info_accepts_split_and_combined_formats(
        self, temp_dir: Path, separate_streams: bool
    ):
        """Run real yt-dlp selection against post-live and combined formats."""
        downloader = VideoDownloader(output_dir=str(temp_dir))
        formats = (
            [
                {
                    "format_id": "299",
                    "url": "https://example.com/video.mp4",
                    "ext": "mp4",
                    "height": 1080,
                    "vcodec": "avc1",
                    "acodec": "none",
                },
                {
                    "format_id": "140",
                    "url": "https://example.com/audio.m4a",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a",
                },
            ]
            if separate_streams
            else [
                {
                    "format_id": "22",
                    "url": "https://example.com/combined.mp4",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                }
            ]
        )

        def extract_info(ydl, url, download=False):
            return ydl.process_ie_result(
                {
                    "id": "JqTSHQwUGAs",
                    "title": "Post-live video",
                    "live_status": "post_live",
                    "formats": formats,
                },
                download=download,
            )

        with (
            patch(
                "src.yt_monitor.media.video_download.get_cookie_options",
                return_value={},
            ),
            patch.object(
                YoutubeDL, "extract_info", autospec=True, side_effect=extract_info
            ),
        ):
            info = downloader.get_video_info(
                "https://www.youtube.com/watch?v=JqTSHQwUGAs"
            )

        assert info["title"] == "Post-live video"
        assert {f["format_id"] for f in info["formats"]} == {
            f["format_id"] for f in formats
        }

    def test_init_creates_output_directory(self, temp_dir: Path):
        """Test that __init__ creates the output directory."""
        output_dir = temp_dir / "downloads"

        VideoDownloader(output_dir=str(output_dir))

        assert output_dir.exists()

    def test_get_format_string_audio_only(self, temp_dir: Path):
        """Test _get_format_string for audio only mode."""
        downloader = VideoDownloader(output_dir=str(temp_dir), audio_only=True)

        format_string = downloader._get_format_string()

        assert format_string == "bestaudio/best"

    def test_get_format_string_best_quality(self, temp_dir: Path):
        """Test _get_format_string for best quality."""
        downloader = VideoDownloader(output_dir=str(temp_dir), quality="best")

        format_string = downloader._get_format_string()

        assert format_string == (
            "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        )

    def test_get_format_string_specific_quality(self, temp_dir: Path):
        """Test _get_format_string for specific quality."""
        downloader = VideoDownloader(output_dir=str(temp_dir), quality="720")

        format_string = downloader._get_format_string()

        assert format_string == (
            "bestvideo[height<=720]+bestaudio[ext=m4a]/"
            "bestvideo[height<=720]+bestaudio/best[height<=720]"
        )

    def test_build_ydl_options_video(self, temp_dir: Path):
        """Test _build_ydl_options for video download."""
        downloader = VideoDownloader(output_dir=str(temp_dir))

        opts = downloader._build_ydl_options("/path/to/output.mp4")

        assert opts["outtmpl"] == "/path/to/output.mp4"
        assert opts["merge_output_format"] == "mp4"
        assert opts["postprocessors"] == [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
        assert opts["postprocessor_args"]["FFmpegVideoConvertor"] == [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
        ]

    def test_build_ydl_options_audio(self, temp_dir: Path):
        """Test _build_ydl_options for audio download."""
        downloader = VideoDownloader(output_dir=str(temp_dir), audio_only=True)

        opts = downloader._build_ydl_options("/path/to/output.mp3")

        assert opts["format"] == "bestaudio/best"
        assert "postprocessors" in opts
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

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
            mock_instance.extract_info.assert_called_once_with(
                "https://www.youtube.com/watch?v=test123", download=False
            )
