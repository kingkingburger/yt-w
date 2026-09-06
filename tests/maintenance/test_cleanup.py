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
    trashed = root / ".trash" / "recoverable.mp4"
    pending_request = root / ".recycle-requests" / "pending.json"
    _write_file_with_age(oldest, age_days=12)
    _write_file_with_age(old, age_days=8)
    _write_file_with_age(recent, age_days=6.9)
    _write_file_with_age(live, age_days=100)
    _write_file_with_age(trashed, age_days=100)
    _write_file_with_age(pending_request, age_days=100)

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


def test_find_old_files_skips_files_that_vanish_between_scan_and_stat(
    tmp_path: Path, initialized_logger, monkeypatch: pytest.MonkeyPatch
):
    """분할 업로드가 .part를 교체하는 사이에 사라진 항목이 정리 회차를 깨면 안 된다."""
    root = tmp_path / "downloads"
    vanishing = root / "uploads" / ".upload-abc.part"
    old = root / "old.mp4"
    _write_file_with_age(vanishing, age_days=9)
    _write_file_with_age(old, age_days=8)

    original_is_file = Path.is_file

    def is_file_then_vanish(path: Path, *args, **kwargs) -> bool:
        result = original_is_file(path, *args, **kwargs)
        if result and path == vanishing:
            path.unlink()
        return result

    monkeypatch.setattr(Path, "is_file", is_file_then_vanish)
    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        found = FileCleaner(str(root), retention_days=7).find_old_files()

    assert [path for path, _age in found] == [old]


def test_cleanup_summary_counts_vanished_file_as_zero_bytes(
    tmp_path: Path, initialized_logger, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "downloads"
    old = root / "old.mp4"
    vanishing = root / "gone.mp4"
    _write_file_with_age(old, age_days=8, content=b"old!")
    _write_file_with_age(vanishing, age_days=9, content=b"gone soon")
    cleaner = FileCleaner(str(root), retention_days=7)
    original_find_old_files = cleaner.find_old_files

    def find_then_vanish() -> list[tuple[Path, float]]:
        found = original_find_old_files()
        vanishing.unlink()
        return found

    monkeypatch.setattr(cleaner, "find_old_files", find_then_vanish)
    with patch("src.yt_monitor.maintenance.cleanup.time.time", return_value=NOW):
        summary = cleaner.get_cleanup_summary()

    assert summary["files_to_delete"] == 2
    assert summary["total_size_bytes"] == 4
