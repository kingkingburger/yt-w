"""Tests for YouTube client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.yt_monitor.youtube_client import YouTubeClient, LiveStreamInfo
from src.yt_monitor.logger import Logger


class TestLiveStreamInfo:
    """Test LiveStreamInfo dataclass."""

    def test_create_with_full_url(self):
        """Test creating LiveStreamInfo with full URL."""
        info = LiveStreamInfo(
            video_id="test123",
            url="https://www.youtube.com/watch?v=test123",
            title="Test Stream"
        )

        assert info.video_id == "test123"
        assert info.url == "https://www.youtube.com/watch?v=test123"
        assert info.title == "Test Stream"

    def test_create_with_partial_url(self):
        """Test that partial URL is converted to full URL."""
        info = LiveStreamInfo(
            video_id="test123",
            url="test123"
        )

        assert info.url == "https://www.youtube.com/watch?v=test123"

    def test_url_already_has_http(self):
        """Test that full URL is not modified."""
        info = LiveStreamInfo(
            video_id="test123",
            url="https://www.youtube.com/watch?v=test123"
        )

        assert info.url == "https://www.youtube.com/watch?v=test123"


class TestYouTubeClient:
    """Test YouTubeClient class."""

    @pytest.fixture(autouse=True)
    def setup_logger(self, tmp_path):
        """Setup logger for tests."""
        log_file = tmp_path / "test.log"
        Logger.initialize(str(log_file))
        yield
        Logger._initialized = False
        Logger._instance = None

    @pytest.fixture
    def client(self):
        """Create a YouTubeClient instance for testing."""
        return YouTubeClient()

    @pytest.fixture
    def mock_ydl(self):
        """Create a mock yt_dlp.YoutubeDL instance."""
        return MagicMock()

    def test_initialization(self):
        """Test client initialization."""
        client = YouTubeClient()
        assert client.logger is not None

    @patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
    def test_check_if_live_endpoint_success(self, mock_ydl_class, client):
        """Test successful live detection via /live endpoint."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            'is_live': True,
            'id': 'abc123',
            'title': 'Live Stream'
        }
        mock_ydl_class.return_value = mock_ydl

        is_live, info = client.check_if_live("https://www.youtube.com/@test")

        assert is_live is True
        assert info is not None
        assert info.video_id == 'abc123'
        assert info.title == 'Live Stream'

    @patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
    def test_check_if_live_not_live(self, mock_ydl_class, client):
        """Test when channel is not live."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            'is_live': False,
            'id': 'abc123'
        }
        mock_ydl_class.return_value = mock_ydl

        is_live, info = client.check_if_live("https://www.youtube.com/@test")

        assert is_live is False
        assert info is None

    @patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
    def test_check_if_live_streams_tab_success(self, mock_ydl_class, client):
        """Test successful live detection via /streams tab."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)

        # First call fails (/live endpoint)
        # Second call succeeds (/streams tab)
        mock_ydl.extract_info.side_effect = [
            Exception("Not found"),
            {
                'entries': [
                    {'id': 'xyz789', 'is_live': True, 'title': 'Stream Title'}
                ]
            }
        ]
        mock_ydl_class.return_value = mock_ydl

        is_live, info = client.check_if_live("https://www.youtube.com/@test")

        assert is_live is True
        assert info is not None
        assert info.video_id == 'xyz789'

    @patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
    def test_check_if_live_all_methods_fail(self, mock_ydl_class, client):
        """Test when all detection methods fail."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("Network error")
        mock_ydl_class.return_value = mock_ydl

        is_live, info = client.check_if_live("https://www.youtube.com/@test")

        assert is_live is False
        assert info is None

    @patch('src.yt_monitor.youtube_client.yt_dlp.YoutubeDL')
    def test_check_if_live_skips_invalid_entries(self, mock_ydl_class, client):
        """Test that invalid entries are skipped."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl.__exit__ = Mock(return_value=False)

        mock_ydl.extract_info.side_effect = [
            Exception("Not found"),
            {
                'entries': [
                    None,  # Invalid entry
                    {},  # Entry without id
                    {'id': 'valid123', 'is_live': True, 'title': 'Valid Stream'}
                ]
            }
        ]
        mock_ydl_class.return_value = mock_ydl

        is_live, info = client.check_if_live("https://www.youtube.com/@test")

        assert is_live is True
        assert info.video_id == 'valid123'
