"""Channel and global-settings model contracts."""

import pytest

from src.yt_monitor.channels.models import ChannelDTO, GlobalSettingsDTO


class TestChannelDTO:
    """Test cases for ChannelDTO dataclass."""

    def test_channel_dto_defaults(self):
        """사용자가 생략한 운영 필드는 안전한 기본값을 사용한다."""
        channel = ChannelDTO(
            id="test-id",
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        assert channel.enabled is True
        assert "bestvideo" in channel.download_format

    def test_channel_dto_validation_empty_url(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="Channel URL cannot be empty"):
            ChannelDTO(id="test-id", name="Test Channel", url="")

    def test_channel_dto_validation_empty_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Channel name cannot be empty"):
            ChannelDTO(id="test-id", name="", url="https://www.youtube.com/@Test")


class TestGlobalSettingsDTO:
    """Test cases for GlobalSettingsDTO dataclass."""

    def test_global_settings_defaults(self):
        """Test GlobalSettingsDTO default values."""
        settings = GlobalSettingsDTO()

        assert settings.check_interval_seconds == 60
        assert settings.download_directory == "./downloads"
        assert settings.log_file == "./logs/live_monitor.log"
        assert settings.split_mode == "time"
        assert settings.split_time_minutes == 30
        assert settings.split_size_mb == 500

    def test_global_settings_validation_invalid_check_interval(self):
        """Test that check_interval_seconds < 1 raises ValueError."""
        with pytest.raises(
            ValueError, match="check_interval_seconds must be at least 1"
        ):
            GlobalSettingsDTO(check_interval_seconds=0)

    def test_global_settings_validation_invalid_split_mode(self):
        """Test that invalid split_mode raises ValueError."""
        with pytest.raises(ValueError, match="split_mode must be"):
            GlobalSettingsDTO(split_mode="invalid")

    def test_global_settings_valid_split_modes(self):
        """Test all valid split_mode values."""
        for mode in ["time", "size", "none"]:
            settings = GlobalSettingsDTO(split_mode=mode)
            assert settings.split_mode == mode
