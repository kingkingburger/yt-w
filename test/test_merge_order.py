"""Merge ordering regression tests."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.yt_monitor import video_merger
from src.yt_monitor.video_merger import MergeJobManager


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


def test_frontend_name_sort_uses_natural_filename_order():
    """The merge sequence name-sort must order 1, 2, 10 naturally."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend sort regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    match = re.search(
        r"function sortSequenceByName\(\) \{[\s\S]*?\n\}",
        app_js,
    )
    assert match is not None

    script = f"""
const state = {{
  sequence: [
    'clips/10.mp4',
    'clips/2.mp4',
    'archive/1.mp4',
    'clips/1.mp4'
  ]
}};
function renderSequence() {{}}
{match.group(0)}
sortSequenceByName();
console.log(JSON.stringify(state.sequence));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        "archive/1.mp4",
        "clips/1.mp4",
        "clips/2.mp4",
        "clips/10.mp4",
    ]
