"""Shared monitor daemon status file.

The Docker compose setup runs the long-lived recorder in the `yt-monitor`
container and the UI/API in `yt-web`. They share the logs volume, so a small
heartbeat file is enough for yt-web to report whether the recorder daemon is
alive without mounting the Docker socket into the web container.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


STATUS_FILENAME = "monitor_status.json"
DEFAULT_STALE_AFTER_SECONDS = 30.0


def get_status_path(log_file: str) -> Path:
    """Return the status file path next to the configured log file."""
    return Path(log_file).parent / STATUS_FILENAME


def write_monitor_status(
    log_file: str,
    *,
    state: str,
    active_channels: int,
    total_channels: int,
    message: str = "",
) -> None:
    """Write monitor daemon status atomically."""
    status_path = get_status_path(log_file)
    status_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "source": "yt-monitor",
        "state": state,
        "active_channels": active_channels,
        "total_channels": total_channels,
        "message": message,
        "updated_at": time.time(),
        "pid": os.getpid(),
        "hostname": os.environ.get("HOSTNAME", ""),
    }

    fd, temp_path = tempfile.mkstemp(
        prefix=f".{STATUS_FILENAME}.",
        dir=str(status_path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False)
        os.replace(temp_path, status_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def read_monitor_status(
    log_file: str,
    *,
    now: Optional[float] = None,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> Dict[str, Any]:
    """Read monitor daemon status and mark stale/missing heartbeats."""
    now = time.time() if now is None else now
    status_path = get_status_path(log_file)

    base = {
        "source": "yt-monitor",
        "state": "missing",
        "is_running": False,
        "active_channels": None,
        "total_channels": None,
        "last_seen": None,
        "age_seconds": None,
        "stale": True,
        "message": "yt-monitor heartbeat not found",
    }

    if not status_path.exists():
        return base

    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            **base,
            "state": "invalid",
            "message": "yt-monitor heartbeat is unreadable",
        }

    updated_at = data.get("updated_at")
    age_seconds = None
    stale = True
    if isinstance(updated_at, (int, float)):
        age_seconds = max(0.0, now - float(updated_at))
        stale = age_seconds > stale_after_seconds

    state = str(data.get("state", "unknown"))
    return {
        "source": str(data.get("source", "yt-monitor")),
        "state": state,
        "is_running": state == "running" and not stale,
        "active_channels": (
            data.get("active_channels")
            if isinstance(data.get("active_channels"), int)
            else None
        ),
        "total_channels": (
            data.get("total_channels")
            if isinstance(data.get("total_channels"), int)
            else None
        ),
        "last_seen": updated_at if isinstance(updated_at, (int, float)) else None,
        "age_seconds": age_seconds,
        "stale": stale,
        "message": str(data.get("message", "")),
    }
