"""Shared pytest fixtures for yt_monitor tests."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

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
    Logger.initialize(str(temp_log_file))
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
def discord_mock_urlopen():
    """Discord Webhook urlopen mock — urllib 호출을 가로채는 공용 fixture."""
    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.__enter__ = lambda s: mock_response
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
        yield mock_open


