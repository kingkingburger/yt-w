"""Regression tests for 2026-04-08 bugs.

Bug 1: _is_entry_live only checked is_live, missed live_status field
Bug 2: _build_ffmpeg_headers was missing, ffmpeg got no HTTP headers -> 403
"""

from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.youtube_client import YouTubeClient
from src.yt_monitor.stream_downloader import StreamDownloader


class TestIsEntryLive:
    """Direct unit tests for _is_entry_live predicate.

    yt-dlp uses 'is_live' for full extraction but 'live_status' for
    extract_flat mode. Both must be checked.
    """

    def test_is_live_true(self):
        assert YouTubeClient._is_entry_live({"is_live": True}) is True

    def test_live_status_is_live(self):
        """The exact case that caused the production bug."""
        assert YouTubeClient._is_entry_live({"live_status": "is_live"}) is True

    def test_live_status_with_is_live_none(self):
        """yt-dlp extract_flat mode: is_live=None, live_status present."""
        assert YouTubeClient._is_entry_live(
            {"is_live": None, "live_status": "is_live"}
        ) is True

    def test_live_status_with_is_live_false(self):
        """live_status takes over when is_live is falsy."""
        assert YouTubeClient._is_entry_live(
            {"is_live": False, "live_status": "is_live"}
        ) is True

    def test_not_live_neither_field(self):
        assert YouTubeClient._is_entry_live({"id": "abc"}) is False

    def test_live_status_was_live(self):
        assert YouTubeClient._is_entry_live({"live_status": "was_live"}) is False

    def test_live_status_is_upcoming(self):
        assert YouTubeClient._is_entry_live({"live_status": "is_upcoming"}) is False

    def test_empty_dict(self):
        assert YouTubeClient._is_entry_live({}) is False

    def test_is_live_false_no_live_status(self):
        assert YouTubeClient._is_entry_live({"is_live": False}) is False


class TestBuildFfmpegHeaders:
    """Direct unit tests for _build_ffmpeg_headers.

    ffmpeg needs HTTP headers (User-Agent, Cookie) to download
    YouTube HLS segments. Without them, 403 Forbidden.
    """

    def test_empty_when_no_headers(self):
        assert StreamDownloader._build_ffmpeg_headers({}) == []

    def test_empty_when_key_missing(self):
        assert StreamDownloader._build_ffmpeg_headers({"url": "x"}) == []

    def test_empty_when_headers_dict_empty(self):
        assert StreamDownloader._build_ffmpeg_headers({"http_headers": {}}) == []

    def test_formats_headers_correctly(self):
        info = {
            "http_headers": {
                "User-Agent": "Mozilla/5.0",
                "Cookie": "abc=123",
            }
        }
        result = StreamDownloader._build_ffmpeg_headers(info)

        assert len(result) == 2
        assert result[0] == "-headers"
        assert "User-Agent: Mozilla/5.0\r\n" in result[1]
        assert "Cookie: abc=123\r\n" in result[1]

    def test_single_header(self):
        info = {"http_headers": {"User-Agent": "test"}}
        result = StreamDownloader._build_ffmpeg_headers(info)

        assert result == ["-headers", "User-Agent: test\r\n"]


class TestStreamsTabLiveStatusRegression:
    """Integration-level regression: _check_streams_tab must detect live_status field."""

    @pytest.fixture
    def youtube_client(self, initialized_logger) -> YouTubeClient:
        return YouTubeClient()

    def test_detects_live_status_field(self, youtube_client: YouTubeClient):
        """Regression: yt-dlp extract_flat returns live_status, not is_live."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "entries": [
                    {"id": "vid1", "live_status": "was_live", "title": "Old"},
                    {"id": "vid2", "live_status": "is_live", "title": "Now Live"},
                ]
            }
            mock_ydl.return_value = mock_instance

            result = youtube_client._check_streams_tab(
                "https://www.youtube.com/@TestChannel"
            )

            assert result is not None
            assert result.video_id == "vid2"
            assert result.title == "Now Live"

    def test_skips_was_live_entries(self, youtube_client: YouTubeClient):
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "entries": [
                    {"id": "vid1", "live_status": "was_live", "title": "Old"},
                    {"id": "vid2", "live_status": "is_upcoming", "title": "Soon"},
                ]
            }
            mock_ydl.return_value = mock_instance

            result = youtube_client._check_streams_tab(
                "https://www.youtube.com/@TestChannel"
            )

            assert result is None


class TestFfmpegHeadersInDownload:
    """Integration: ffmpeg command must include -headers before -i."""

    @pytest.fixture
    def downloader(self, temp_dir, initialized_logger) -> StreamDownloader:
        return StreamDownloader(
            download_directory=str(temp_dir / "downloads"),
            download_format="bestvideo+bestaudio/best",
            split_mode="time",
            split_time_minutes=10,
        )

    def test_dual_stream_includes_headers(self, downloader: StreamDownloader):
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "requested_formats": [
                    {
                        "url": "https://video-url.com",
                        "http_headers": {"User-Agent": "Mozilla/5.0"},
                    },
                    {
                        "url": "https://audio-url.com",
                        "http_headers": {"User-Agent": "Mozilla/5.0"},
                    },
                ],
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

                downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test",
                    "/output/%03d.mp4",
                )

                cmd = mock_run.call_args[0][0]
                headers_indices = [i for i, a in enumerate(cmd) if a == "-headers"]
                input_indices = [i for i, a in enumerate(cmd) if a == "-i"]

                assert len(headers_indices) == 2, "Each input needs its own -headers"
                for h_idx, i_idx in zip(headers_indices, input_indices):
                    assert h_idx < i_idx, "-headers must precede its -i input"

    def test_single_stream_includes_headers(self, downloader: StreamDownloader):
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "url": "https://direct-url.com",
                "http_headers": {"User-Agent": "Mozilla/5.0"},
            }
            mock_ydl.return_value = mock_instance

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

                downloader._download_with_realtime_split(
                    "https://www.youtube.com/watch?v=test",
                    "/output/%03d.mp4",
                )

                cmd = mock_run.call_args[0][0]
                assert "-headers" in cmd, "Headers must be passed to ffmpeg"
                h_idx = cmd.index("-headers")
                i_idx = cmd.index("-i")
                assert h_idx < i_idx
