import os
from pathlib import Path

from src.yt_monitor.youtube.history import UploadHistory


def test_history_survives_reopening_and_ignores_replaced_or_deleted_files(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    stat = source.stat()
    UploadHistory(tmp_path).record("clip.mp4", stat.st_size, stat.st_mtime_ns, "video")
    history = UploadHistory(tmp_path)
    assert history.list_current() == [{"source": "clip.mp4", "video_id": "video"}]
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert history.list_current() == []
    source.unlink()
    assert history.list_current() == []


def test_empty_history_does_not_create_files(tmp_path: Path):
    assert UploadHistory(tmp_path).list_current() == []
    assert list(tmp_path.iterdir()) == []


def test_history_keeps_other_successes_and_latest_video_for_same_source(tmp_path: Path):
    history = UploadHistory(tmp_path)
    for name in ("one.mp4", "two.mp4"):
        source = tmp_path / name
        source.write_bytes(b"video")
        stat = source.stat()
        history.record(name, stat.st_size, stat.st_mtime_ns, "first")
        history.record(name, stat.st_size, stat.st_mtime_ns, "latest")
    assert sorted(history.list_current(), key=lambda item: item["source"]) == [
        {"source": "one.mp4", "video_id": "latest"},
        {"source": "two.mp4", "video_id": "latest"},
    ]
