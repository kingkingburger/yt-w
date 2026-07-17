"""Shared fixtures for monitoring service and worker tests."""

from pathlib import Path

import pytest

from src.yt_monitor.channels.models import ChannelDTO, GlobalSettingsDTO


@pytest.fixture
def sample_channel() -> ChannelDTO:
    return ChannelDTO(
        id="test-channel-id",
        name="Test Channel",
        url="https://www.youtube.com/@TestChannel",
        enabled=True,
    )


@pytest.fixture
def global_settings(temp_dir: Path) -> GlobalSettingsDTO:
    return GlobalSettingsDTO(
        check_interval_seconds=1,
        download_directory=str(temp_dir / "downloads"),
        log_file=str(temp_dir / "test.log"),
        split_mode="time",
        split_time_minutes=30,
    )
