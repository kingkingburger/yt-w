"""Shared FastAPI fixtures for web tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.web.app import WebAPI


@pytest.fixture
def channels_file(temp_channels_file: Path) -> str:
    return str(temp_channels_file)


@pytest.fixture
def client(channels_file: str) -> TestClient:
    return TestClient(WebAPI(channels_file=channels_file).app)
