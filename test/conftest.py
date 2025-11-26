"""Shared pytest fixtures for yt_monitor tests."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.yt_monitor.logger import Logger


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    # Windows-safe cleanup: ignore errors on file deletion
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_log_file(temp_dir: Path) -> Path:
    """Create a temporary log file path."""
    return temp_dir / "test.log"


@pytest.fixture
def initialized_logger(temp_log_file: Path) -> Generator[None, None, None]:
    """Initialize logger for tests and reset after."""
    Logger._initialized = False
    Logger._instance = None
    logger = Logger.initialize(str(temp_log_file))
    yield
    # Close all handlers to release file locks on Windows
    if Logger._instance:
        for handler in Logger._instance.handlers[:]:
            handler.close()
            Logger._instance.removeHandler(handler)
    Logger._initialized = False
    Logger._instance = None


@pytest.fixture
def temp_channels_file(temp_dir: Path) -> Path:
    """Create a temporary channels.json file."""
    channels_file = temp_dir / "channels.json"
    default_data = {
        "channels": [],
        "global_settings": {
            "check_interval_seconds": 60,
            "download_directory": str(temp_dir / "downloads"),
            "log_file": str(temp_dir / "monitor.log"),
            "split_mode": "time",
            "split_time_minutes": 30,
            "split_size_mb": 500,
        },
    }
    with open(channels_file, "w", encoding="utf-8") as f:
        json.dump(default_data, f)
    return channels_file


@pytest.fixture
def sample_channel_data() -> dict:
    """Sample channel data for testing."""
    return {
        "id": "test-channel-id-123",
        "name": "Test Channel",
        "url": "https://www.youtube.com/@TestChannel",
        "enabled": True,
        "download_format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    }


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """Create a temporary config.json file."""
    config_file = temp_dir / "config.json"
    config_data = {
        "channel_url": "https://www.youtube.com/@TestChannel",
        "check_interval_seconds": 60,
        "download_directory": str(temp_dir / "downloads"),
        "log_file": str(temp_dir / "monitor.log"),
        "video_quality": "best",
        "download_format": "bestvideo+bestaudio/best",
        "split_mode": "time",
        "split_time_minutes": 30,
        "split_size_mb": 500,
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
    return config_file
