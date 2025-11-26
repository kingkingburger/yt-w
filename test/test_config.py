"""Tests for config module."""

import json
from pathlib import Path

import pytest

from src.yt_monitor.config import Config, ConfigLoader


class TestConfig:
    """Test cases for Config dataclass."""

    def test_config_creation_with_valid_data(self):
        """Test Config creation with valid data."""
        config = Config(
            channel_url="https://www.youtube.com/@TestChannel",
            check_interval_seconds=60,
            download_directory="./downloads",
            log_file="./test.log",
            video_quality="best",
            download_format="bestvideo+bestaudio/best",
        )

        assert config.channel_url == "https://www.youtube.com/@TestChannel"
        assert config.check_interval_seconds == 60
        assert config.download_directory == "./downloads"
        assert config.log_file == "./test.log"

    def test_config_default_split_values(self):
        """Test Config default split mode values."""
        config = Config(
            channel_url="https://www.youtube.com/@TestChannel",
            check_interval_seconds=60,
            download_directory="./downloads",
            log_file="./test.log",
            video_quality="best",
            download_format="bestvideo+bestaudio/best",
        )

        assert config.split_mode == "time"
        assert config.split_time_minutes == 30
        assert config.split_size_mb == 500

    def test_config_validation_empty_channel_url(self):
        """Test that empty channel_url raises ValueError."""
        with pytest.raises(ValueError, match="channel_url cannot be empty"):
            Config(
                channel_url="",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
            )

    def test_config_validation_invalid_check_interval(self):
        """Test that check_interval_seconds < 1 raises ValueError."""
        with pytest.raises(
            ValueError, match="check_interval_seconds must be at least 1"
        ):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=0,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
            )

    def test_config_validation_empty_download_directory(self):
        """Test that empty download_directory raises ValueError."""
        with pytest.raises(ValueError, match="download_directory cannot be empty"):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=60,
                download_directory="",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
            )

    def test_config_validation_empty_log_file(self):
        """Test that empty log_file raises ValueError."""
        with pytest.raises(ValueError, match="log_file cannot be empty"):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
            )

    def test_config_validation_invalid_split_mode(self):
        """Test that invalid split_mode raises ValueError."""
        with pytest.raises(ValueError, match="split_mode must be"):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
                split_mode="invalid",
            )

    def test_config_validation_invalid_split_time_minutes(self):
        """Test that split_time_minutes < 1 raises ValueError."""
        with pytest.raises(ValueError, match="split_time_minutes must be at least 1"):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
                split_time_minutes=0,
            )

    def test_config_validation_invalid_split_size_mb(self):
        """Test that split_size_mb < 1 raises ValueError."""
        with pytest.raises(ValueError, match="split_size_mb must be at least 1"):
            Config(
                channel_url="https://www.youtube.com/@TestChannel",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="bestvideo+bestaudio/best",
                split_size_mb=0,
            )


class TestConfigLoader:
    """Test cases for ConfigLoader class."""

    def test_load_from_file(self, temp_config_file: Path):
        """Test loading config from file."""
        config = ConfigLoader.load(str(temp_config_file))

        assert config.channel_url == "https://www.youtube.com/@TestChannel"
        assert config.check_interval_seconds == 60

    def test_load_file_not_found(self):
        """Test that loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            ConfigLoader.load("nonexistent.json")

    def test_load_invalid_json(self, temp_dir: Path):
        """Test that loading invalid JSON raises ValueError."""
        invalid_file = temp_dir / "invalid.json"
        invalid_file.write_text("not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            ConfigLoader.load(str(invalid_file))

    def test_load_uses_defaults_for_missing_keys(self, temp_dir: Path):
        """Test that missing keys use default values."""
        partial_config = temp_dir / "partial.json"
        partial_config.write_text(
            json.dumps({"channel_url": "https://www.youtube.com/@TestChannel"})
        )

        config = ConfigLoader.load(str(partial_config))

        assert config.check_interval_seconds == 60  # default
        assert config.download_directory == "./downloads"  # default

    def test_load_dict(self):
        """Test loading config from dictionary."""
        config_dict = {
            "channel_url": "https://www.youtube.com/@TestChannel",
            "check_interval_seconds": 120,
        }

        config = ConfigLoader.load_dict(config_dict)

        assert config.channel_url == "https://www.youtube.com/@TestChannel"
        assert config.check_interval_seconds == 120
        assert config.download_directory == "./downloads"  # default

    def test_load_dict_overrides_defaults(self):
        """Test that provided values override defaults."""
        config_dict = {
            "channel_url": "https://www.youtube.com/@TestChannel",
            "download_directory": "/custom/path",
        }

        config = ConfigLoader.load_dict(config_dict)

        assert config.download_directory == "/custom/path"
