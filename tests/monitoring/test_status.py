"""Shared monitor heartbeat file contracts."""

import json
from pathlib import Path

import pytest

from src.yt_monitor.monitoring.status import (
    get_status_path,
    read_monitor_status,
    write_monitor_status,
)


def test_write_and_read_status_round_trip_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    log_file = str(tmp_path / "logs" / "monitor.log")
    monkeypatch.setattr("src.yt_monitor.monitoring.status.time.time", lambda: 100.0)
    monkeypatch.setattr("src.yt_monitor.monitoring.status.os.getpid", lambda: 4321)
    monkeypatch.setenv("HOSTNAME", "monitor-test")

    write_monitor_status(
        log_file,
        state="running",
        active_channels=2,
        total_channels=3,
        message="healthy",
    )

    status = read_monitor_status(log_file, now=110.0)
    assert status == {
        "source": "yt-monitor",
        "state": "running",
        "is_running": True,
        "active_channels": 2,
        "total_channels": 3,
        "last_seen": 100.0,
        "age_seconds": 10.0,
        "stale": False,
        "message": "healthy",
    }
    assert list(get_status_path(log_file).parent.glob(".monitor_status.json.*")) == []


@pytest.mark.parametrize(
    ("now", "expected_stale", "expected_running"),
    [(130.0, False, True), (130.001, True, False)],
)
def test_status_staleness_boundary(
    tmp_path: Path,
    now: float,
    expected_stale: bool,
    expected_running: bool,
):
    log_file = str(tmp_path / "monitor.log")
    get_status_path(log_file).write_text(
        json.dumps({"state": "running", "updated_at": 100.0}),
        encoding="utf-8",
    )

    status = read_monitor_status(log_file, now=now, stale_after_seconds=30.0)

    assert status["stale"] is expected_stale
    assert status["is_running"] is expected_running


def test_invalid_json_is_reported_as_unreadable(tmp_path: Path):
    log_file = str(tmp_path / "monitor.log")
    get_status_path(log_file).write_text("{broken", encoding="utf-8")

    status = read_monitor_status(log_file, now=100.0)

    assert status["state"] == "invalid"
    assert status["is_running"] is False
    assert status["message"] == "yt-monitor heartbeat is unreadable"


def test_malformed_field_types_do_not_claim_valid_channel_counts(tmp_path: Path):
    log_file = str(tmp_path / "monitor.log")
    get_status_path(log_file).write_text(
        json.dumps(
            {
                "state": "running",
                "updated_at": "not-a-timestamp",
                "active_channels": True,
                "total_channels": -3,
            }
        ),
        encoding="utf-8",
    )

    status = read_monitor_status(log_file, now=100.0)

    assert status["is_running"] is False
    assert status["last_seen"] is None
    assert status["active_channels"] is None
    assert status["total_channels"] is None
