"""Tests for channel_manager module."""

from pathlib import Path

import pytest

from src.yt_monitor.channel_manager import (
    ChannelDTO,
    GlobalSettingsDTO,
    ChannelManager,
)


class TestChannelDTO:
    """Test cases for ChannelDTO dataclass."""

    def test_channel_dto_creation(self):
        """Test ChannelDTO creation with valid data."""
        channel = ChannelDTO(
            id="test-id",
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        assert channel.id == "test-id"
        assert channel.name == "Test Channel"
        assert channel.url == "https://www.youtube.com/@TestChannel"
        assert channel.enabled is True  # default
        assert "bestvideo" in channel.download_format  # default

    def test_channel_dto_validation_empty_url(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="Channel URL cannot be empty"):
            ChannelDTO(id="test-id", name="Test Channel", url="")

    def test_channel_dto_validation_empty_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Channel name cannot be empty"):
            ChannelDTO(id="test-id", name="", url="https://www.youtube.com/@Test")

    def test_channel_dto_custom_format(self):
        """Test ChannelDTO with custom download format."""
        channel = ChannelDTO(
            id="test-id",
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
            download_format="bestvideo[height<=1080]+bestaudio",
        )

        assert channel.download_format == "bestvideo[height<=1080]+bestaudio"


class TestGlobalSettingsDTO:
    """Test cases for GlobalSettingsDTO dataclass."""

    def test_global_settings_defaults(self):
        """Test GlobalSettingsDTO default values."""
        settings = GlobalSettingsDTO()

        assert settings.check_interval_seconds == 60
        assert settings.download_directory == "./downloads"
        assert settings.log_file == "./live_monitor.log"
        assert settings.split_mode == "time"
        assert settings.split_time_minutes == 30
        assert settings.split_size_mb == 500

    def test_global_settings_custom_values(self):
        """Test GlobalSettingsDTO with custom values."""
        settings = GlobalSettingsDTO(
            check_interval_seconds=120,
            download_directory="/custom/downloads",
            split_mode="size",
        )

        assert settings.check_interval_seconds == 120
        assert settings.download_directory == "/custom/downloads"
        assert settings.split_mode == "size"

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


class TestChannelManager:
    """Test cases for ChannelManager class."""

    def test_init_creates_file_if_not_exists(self, temp_dir: Path):
        """Test that ChannelManager creates channels file if it doesn't exist."""
        channels_file = temp_dir / "new_channels.json"

        ChannelManager(channels_file=str(channels_file))

        assert channels_file.exists()

    def test_init_uses_existing_file(self, temp_channels_file: Path):
        """Test that ChannelManager uses existing channels file."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        channels = manager.list_channels()
        assert channels == []  # Empty by default

    def test_add_channel(self, temp_channels_file: Path):
        """Test adding a new channel."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        channel = manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        assert channel.name == "Test Channel"
        assert channel.url == "https://www.youtube.com/@TestChannel"
        assert channel.id is not None
        assert channel.enabled is True

    def test_add_channel_with_custom_format(self, temp_channels_file: Path):
        """Test adding a channel with custom download format."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        channel = manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
            download_format="bestvideo[height<=1080]+bestaudio",
        )

        assert channel.download_format == "bestvideo[height<=1080]+bestaudio"

    def test_add_channel_duplicate_url_raises_error(self, temp_channels_file: Path):
        """Test that adding duplicate URL raises ValueError."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        with pytest.raises(ValueError, match="already exists"):
            manager.add_channel(
                name="Another Channel",
                url="https://www.youtube.com/@TestChannel",
            )

    def test_remove_channel(self, temp_channels_file: Path):
        """Test removing a channel."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        channel = manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        result = manager.remove_channel(channel.id)

        assert result is True
        assert manager.list_channels() == []

    def test_remove_channel_not_found(self, temp_channels_file: Path):
        """Test removing a non-existent channel."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        result = manager.remove_channel("nonexistent-id")

        assert result is False

    def test_list_channels(self, temp_channels_file: Path):
        """Test listing all channels."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        manager.add_channel(name="Channel 1", url="https://www.youtube.com/@Channel1")
        manager.add_channel(name="Channel 2", url="https://www.youtube.com/@Channel2")

        channels = manager.list_channels()

        assert len(channels) == 2

    def test_list_channels_enabled_only(self, temp_channels_file: Path):
        """Test listing only enabled channels."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        manager.add_channel(
            name="Enabled", url="https://www.youtube.com/@Enabled", enabled=True
        )
        manager.add_channel(
            name="Disabled", url="https://www.youtube.com/@Disabled", enabled=False
        )

        channels = manager.list_channels(enabled_only=True)

        assert len(channels) == 1
        assert channels[0].name == "Enabled"

    def test_get_channel(self, temp_channels_file: Path):
        """Test getting a specific channel by ID."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        added_channel = manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        channel = manager.get_channel(added_channel.id)

        assert channel is not None
        assert channel.id == added_channel.id
        assert channel.name == "Test Channel"

    def test_get_channel_not_found(self, temp_channels_file: Path):
        """Test getting a non-existent channel."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        channel = manager.get_channel("nonexistent-id")

        assert channel is None

    def test_update_channel(self, temp_channels_file: Path):
        """Test updating channel information."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        channel = manager.add_channel(
            name="Original Name",
            url="https://www.youtube.com/@TestChannel",
        )

        updated = manager.update_channel(channel.id, name="Updated Name")

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.url == "https://www.youtube.com/@TestChannel"

    def test_update_channel_enabled_status(self, temp_channels_file: Path):
        """Test updating channel enabled status."""
        manager = ChannelManager(channels_file=str(temp_channels_file))
        channel = manager.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
            enabled=True,
        )

        updated = manager.update_channel(channel.id, enabled=False)

        assert updated is not None
        assert updated.enabled is False

    def test_update_channel_not_found(self, temp_channels_file: Path):
        """Test updating a non-existent channel."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        result = manager.update_channel("nonexistent-id", name="New Name")

        assert result is None

    def test_get_global_settings(self, temp_channels_file: Path):
        """Test getting global settings."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        settings = manager.get_global_settings()

        assert settings.check_interval_seconds == 60
        assert settings.split_mode == "time"

    def test_update_global_settings(self, temp_channels_file: Path):
        """Test updating global settings."""
        manager = ChannelManager(channels_file=str(temp_channels_file))

        settings = manager.update_global_settings(
            check_interval_seconds=120,
            split_mode="size",
        )

        assert settings.check_interval_seconds == 120
        assert settings.split_mode == "size"

    def test_persistence(self, temp_channels_file: Path):
        """Test that changes are persisted to file."""
        manager1 = ChannelManager(channels_file=str(temp_channels_file))
        manager1.add_channel(
            name="Test Channel",
            url="https://www.youtube.com/@TestChannel",
        )

        # Create new manager instance with same file
        manager2 = ChannelManager(channels_file=str(temp_channels_file))
        channels = manager2.list_channels()

        assert len(channels) == 1
        assert channels[0].name == "Test Channel"
