"""FileCleaner retention, preservation, and failure-isolation contracts."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.yt_monitor.maintenance.cleanup import FileCleaner


NOW = 1_800_000_000.0


def _write_file_with_age(path: Path, *, age_days: float, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    modified_at = NOW - age_days * 24 * 60 * 60
    os.utime(path, (modified_at, modified_at))


def test_find_old_files_excludes_live_and_recent_and_orders_oldest(
    tmp_path: Path, initialized_logger
):
    root = tmp_path / "downloads"
    oldest = root / "archive" / "oldest.mp4"
    old = root / "old.mp4"
    recent = root / "recent.mp4"
    live = root / "live" / "protected.mp4"
    _write_file_with_age(oldest, age_days=12)
    _write_file_with_age(old, age_days=8)
    _write_file_with_age(recent, age_days=6.9)
    _write_file_with_age(live, age_days=100)

    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        found = FileCleaner(str(root), retention_days=7).find_old_files()

    assert [path for path, _age in found] == [oldest, old]
    assert [age for _path, age in found] == pytest.approx([12, 8])


def test_cleanup_dry_run_never_deletes_or_prunes_directories(
    tmp_path: Path, initialized_logger
):
    root = tmp_path / "downloads"
    old = root / "nested" / "old.mp4"
    _write_file_with_age(old, age_days=8)

    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        reported = FileCleaner(str(root), retention_days=7).cleanup(dry_run=True)

    assert reported == [old]
    assert old.exists()
    assert old.parent.exists()


def test_cleanup_continues_after_unlink_error_and_prunes_empty_directories(
    tmp_path: Path, initialized_logger, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "downloads"
    blocked = root / "blocked" / "blocked.mp4"
    deletable = root / "deletable" / "old.mp4"
    _write_file_with_age(blocked, age_days=10)
    _write_file_with_age(deletable, age_days=9)

    original_unlink = Path.unlink

    def fail_one_unlink(path: Path, *args, **kwargs) -> None:
        if path == blocked:
            raise OSError("file is busy")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one_unlink)
    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        deleted = FileCleaner(str(root), retention_days=7).cleanup()

    assert deleted == [deletable]
    assert blocked.exists()
    assert not deletable.exists()
    assert not deletable.parent.exists()


def test_cleanup_summary_counts_only_expired_files_and_reports_live_usage(
    tmp_path: Path, initialized_logger
):
    root = tmp_path / "downloads"
    _write_file_with_age(root / "old.mp4", age_days=8, content=b"old!")
    _write_file_with_age(root / "recent.mp4", age_days=1, content=b"recent")
    _write_file_with_age(root / "live" / "kept.mp4", age_days=30, content=b"live!")

    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        summary = FileCleaner(str(root), retention_days=7).get_cleanup_summary()

    assert summary["files_to_delete"] == 1
    assert summary["total_size_bytes"] == 4
    assert summary["retention_days"] == 7
    assert summary["live_files_preserved"] == 1
    assert summary["live_size_mb"] == pytest.approx(5 / (1024 * 1024))
