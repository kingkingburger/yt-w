"""Tests for configuration module."""

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.yt_monitor.config import Config, ConfigLoader


class TestConfig:
    """Test Config dataclass."""

    def test_valid_config(self):
        """Test creating a valid config."""
        config = Config(
            channel_url="https://www.youtube.com/@test",
            check_interval_seconds=60,
            download_directory="./downloads",
            log_file="./test.log",
            video_quality="best",
            download_format="best",
            split_mode="time",
            split_time_minutes=30,
            split_size_mb=500,
        )

        assert config.channel_url == "https://www.youtube.com/@test"
        assert config.check_interval_seconds == 60
        assert config.split_mode == "time"
        assert config.split_time_minutes == 30
        assert config.split_size_mb == 500

    def test_empty_channel_url_raises_error(self):
        """Test that empty channel_url raises ValueError."""
        with pytest.raises(ValueError, match="channel_url cannot be empty"):
            Config(
                channel_url="",
                check_interval_seconds=60,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="best",
            )

    def test_invalid_check_interval_raises_error(self):
        """Test that check_interval < 1 raises ValueError."""
        with pytest.raises(
            ValueError, match="check_interval_seconds must be at least 1"
        ):
            Config(
                channel_url="https://www.youtube.com/@test",
                check_interval_seconds=0,
                download_directory="./downloads",
                log_file="./test.log",
                video_quality="best",
                download_format="best",
            )

    def test_empty_download_directory_raises_error(self):
        """Test that empty download_directory raises ValueError."""
        with pytest.raises(ValueError, match="download_directory cannot be empty"):
            Config(
                channel_url="https://www.youtube.com/@test",
                check_interval_seconds=60,
                download_directory="",
                log_file="./test.log",
                video_quality="best",
                download_format="best",
            )


class TestConfigLoader:
    """Test ConfigLoader class."""

    def test_load_valid_config_file(self):
        """Test loading a valid configuration file."""
        config_data = {
            "channel_url": "https://www.youtube.com/@test",
            "check_interval_seconds": 120,
            "download_directory": "./test_downloads",
            "log_file": "./test.log",
            "video_quality": "best",
            "download_format": "best",
        }

        with NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = ConfigLoader.load(temp_path)
            assert config.channel_url == "https://www.youtube.com/@test"
            assert config.check_interval_seconds == 120
            assert config.download_directory == "./test_downloads"
        finally:
            Path(temp_path).unlink()

    def test_load_nonexistent_file_raises_error(self):
        """Test that loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load("nonexistent_config.json")

    def test_load_invalid_json_raises_error(self):
        """Test that loading invalid JSON raises ValueError."""
        with NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                ConfigLoader.load(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_dict(self):
        """Test loading configuration from dictionary."""
        config_dict = {
            "channel_url": "https://www.youtube.com/@test",
            "check_interval_seconds": 30,
        }

        config = ConfigLoader.load_dict(config_dict)
        assert config.channel_url == "https://www.youtube.com/@test"
        assert config.check_interval_seconds == 30
        # Check defaults are applied
        assert config.download_directory == "./downloads"
        assert config.log_file == "./live_monitor.log"

    def test_load_dict_with_defaults(self):
        """Test that defaults are merged correctly."""
        config_dict = {"channel_url": "https://www.youtube.com/@test"}

        config = ConfigLoader.load_dict(config_dict)
        assert config.channel_url == "https://www.youtube.com/@test"
        assert config.check_interval_seconds == 60  # default
        assert config.download_directory == "./downloads"  # default
