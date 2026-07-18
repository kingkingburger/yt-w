"""Shared FastAPI fixtures for web tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.maintenance.scheduler import CleanupScheduler
from src.yt_monitor.web.app import WebAPI


@pytest.fixture(autouse=True)
def prevent_cleanup_daemon_in_web_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route tests must not leak one real scheduler thread per WebAPI instance."""
    monkeypatch.setattr(CleanupScheduler, "start", lambda _self: None)


@pytest.fixture
def channels_file(temp_channels_file: Path) -> str:
    return str(temp_channels_file)


@pytest.fixture
def client(channels_file: str) -> TestClient:
    return TestClient(WebAPI(channels_file=channels_file).app)
