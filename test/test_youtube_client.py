"""Tests for youtube_client module."""

from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.youtube_client import YouTubeClient, LiveStreamInfo


class TestLiveStreamInfo:
    """Test cases for LiveStreamInfo dataclass."""

    def test_live_stream_info_creation(self):
        """Test LiveStreamInfo creation with valid data."""
        info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Test Stream",
        )

        assert info.video_id == "abc123"
        assert info.url == "https://www.youtube.com/watch?v=abc123"
        assert info.title == "Test Stream"

    def test_live_stream_info_auto_url(self):
        """Test that URL is auto-generated if not starting with http."""
        info = LiveStreamInfo(
            video_id="abc123",
            url="abc123",
        )

        assert info.url == "https://www.youtube.com/watch?v=abc123"

    def test_live_stream_info_preserves_full_url(self):
        """Test that full URL is preserved."""
        full_url = "https://www.youtube.com/watch?v=xyz789"
        info = LiveStreamInfo(
            video_id="xyz789",
            url=full_url,
        )

        assert info.url == full_url

    def test_live_stream_info_optional_title(self):
        """Test that title is optional."""
        info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
        )

        assert info.title is None


class TestYouTubeClient:
    """Test cases for YouTubeClient class."""

    @pytest.fixture
    def youtube_client(self, initialized_logger) -> YouTubeClient:
        """Create YouTubeClient instance with initialized logger."""
        return YouTubeClient()

    def test_check_if_live_returns_tuple(self, youtube_client: YouTubeClient):
        """Test that check_if_live returns a tuple."""
        with patch.object(youtube_client, "_check_live_endpoint", return_value=None):
            with patch.object(youtube_client, "_check_streams_tab", return_value=None):
                with patch.object(
                    youtube_client, "_check_channel_page", return_value=None
                ):
                    result = youtube_client.check_if_live(
                        "https://www.youtube.com/@TestChannel"
                    )

                    assert isinstance(result, tuple)
                    assert len(result) == 2

    def test_check_if_live_no_stream(self, youtube_client: YouTubeClient):
        """Test check_if_live when no stream is found."""
        with patch.object(youtube_client, "_check_live_endpoint", return_value=None):
            with patch.object(youtube_client, "_check_streams_tab", return_value=None):
                with patch.object(
                    youtube_client, "_check_channel_page", return_value=None
                ):
                    is_live, stream_info = youtube_client.check_if_live(
                        "https://www.youtube.com/@TestChannel"
                    )

                    assert is_live is False
                    assert stream_info is None

    def test_check_if_live_found_via_live_endpoint(self, youtube_client: YouTubeClient):
        """Test check_if_live when stream found via /live endpoint."""
        mock_info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Live Stream",
        )

        with patch.object(
            youtube_client, "_check_live_endpoint", return_value=mock_info
        ):
            is_live, stream_info = youtube_client.check_if_live(
                "https://www.youtube.com/@TestChannel"
            )

            assert is_live is True
            assert stream_info == mock_info

    def test_check_if_live_found_via_streams_tab(self, youtube_client: YouTubeClient):
        """Test check_if_live when stream found via /streams tab."""
        mock_info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Live Stream",
        )

        with patch.object(youtube_client, "_check_live_endpoint", return_value=None):
            with patch.object(
                youtube_client, "_check_streams_tab", return_value=mock_info
            ):
                is_live, stream_info = youtube_client.check_if_live(
                    "https://www.youtube.com/@TestChannel"
                )

                assert is_live is True
                assert stream_info == mock_info

    def test_check_if_live_found_via_channel_page(self, youtube_client: YouTubeClient):
        """Test check_if_live when stream found via channel page."""
        mock_info = LiveStreamInfo(
            video_id="abc123",
            url="https://www.youtube.com/watch?v=abc123",
            title="Live Stream",
        )

        with patch.object(youtube_client, "_check_live_endpoint", return_value=None):
            with patch.object(youtube_client, "_check_streams_tab", return_value=None):
                with patch.object(
                    youtube_client, "_check_channel_page", return_value=mock_info
                ):
                    is_live, stream_info = youtube_client.check_if_live(
                        "https://www.youtube.com/@TestChannel"
                    )

                    assert is_live is True
                    assert stream_info == mock_info

    def test_check_if_live_handles_exception(self, youtube_client: YouTubeClient):
        """Test that check_if_live handles exceptions gracefully."""
        # Create a mock method with __name__ attribute
        mock_method = MagicMock(side_effect=Exception("API Error"))
        mock_method.__name__ = "_check_live_endpoint"

        with patch.object(youtube_client, "_check_live_endpoint", mock_method):
            with patch.object(youtube_client, "_check_streams_tab", return_value=None):
                with patch.object(
                    youtube_client, "_check_channel_page", return_value=None
                ):
                    is_live, stream_info = youtube_client.check_if_live(
                        "https://www.youtube.com/@TestChannel"
                    )

                    assert is_live is False
                    assert stream_info is None

    def test_check_live_endpoint_constructs_correct_url(
        self, youtube_client: YouTubeClient
    ):
        """Test that _check_live_endpoint constructs the correct /live URL."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {"is_live": False}
            mock_ydl.return_value = mock_instance

            youtube_client._check_live_endpoint("https://www.youtube.com/@TestChannel")

            mock_instance.extract_info.assert_called_once_with(
                "https://www.youtube.com/@TestChannel/live", download=False
            )

    def test_check_live_endpoint_strips_trailing_slash(
        self, youtube_client: YouTubeClient
    ):
        """Test that _check_live_endpoint strips trailing slash from URL."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {"is_live": False}
            mock_ydl.return_value = mock_instance

            youtube_client._check_live_endpoint("https://www.youtube.com/@TestChannel/")

            mock_instance.extract_info.assert_called_once_with(
                "https://www.youtube.com/@TestChannel/live", download=False
            )

    def test_check_live_endpoint_returns_info_when_live(
        self, youtube_client: YouTubeClient
    ):
        """Test that _check_live_endpoint returns LiveStreamInfo when live."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "is_live": True,
                "id": "abc123",
                "title": "Test Live Stream",
            }
            mock_ydl.return_value = mock_instance

            result = youtube_client._check_live_endpoint(
                "https://www.youtube.com/@TestChannel"
            )

            assert result is not None
            assert result.video_id == "abc123"
            assert result.title == "Test Live Stream"

    def test_check_streams_tab_returns_none_when_not_live(
        self, youtube_client: YouTubeClient
    ):
        """Test that _check_streams_tab returns None when no live stream."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "entries": [
                    {"id": "video1", "is_live": False},
                    {"id": "video2", "is_live": False},
                ]
            }
            mock_ydl.return_value = mock_instance

            result = youtube_client._check_streams_tab(
                "https://www.youtube.com/@TestChannel"
            )

            assert result is None

    def test_check_streams_tab_returns_info_when_live(
        self, youtube_client: YouTubeClient
    ):
        """Test that _check_streams_tab returns LiveStreamInfo when live."""
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.extract_info.return_value = {
                "entries": [
                    {"id": "video1", "is_live": False},
                    {"id": "live123", "is_live": True, "title": "Live Now"},
                ]
            }
            mock_ydl.return_value = mock_instance

            result = youtube_client._check_streams_tab(
                "https://www.youtube.com/@TestChannel"
            )

            assert result is not None
            assert result.video_id == "live123"
            assert result.title == "Live Now"
