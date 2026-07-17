"""Backend merge ordering and path-safety contracts."""

from pathlib import Path

import pytest

import src.yt_monitor.media.merge as video_merger
from src.yt_monitor.media.merge import MergeJobManager


def test_merge_submit_preserves_requested_input_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The backend must pass the ordered request inputs through to ffmpeg."""
    root = tmp_path / "downloads"
    root.mkdir()
    for name in ["10.mp4", "2.mp4", "1.mp4"]:
        (root / name).write_bytes(b"video")

    thread_args = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.args = args

        def start(self):
            thread_args.append(self.args)

    monkeypatch.setattr(video_merger.threading, "Thread", FakeThread)

    requested = ["10.mp4", "2.mp4", "1.mp4"]
    job = MergeJobManager(root).submit(requested, "out.mp4", "concat")

    assert job.inputs == requested
    assert len(thread_args) == 1
    absolute_inputs = thread_args[0][1]
    assert absolute_inputs == [(root / name).resolve() for name in requested]


def test_merge_rejects_sibling_prefix_path_escape(tmp_path: Path):
    """A sibling path that shares the root prefix must not pass containment."""
    root = tmp_path / "downloads"
    sibling = tmp_path / "downloads_evil"
    root.mkdir()
    sibling.mkdir()
    (root / "a.mp4").write_bytes(b"video")
    (sibling / "b.mp4").write_bytes(b"video")

    with pytest.raises(ValueError, match="잘못된 입력 경로"):
        MergeJobManager(root).submit(
            ["a.mp4", "../downloads_evil/b.mp4"],
            "out.mp4",
            "concat",
        )
