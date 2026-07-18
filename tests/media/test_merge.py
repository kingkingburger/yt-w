"""Backend merge ordering and path-safety contracts."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import src.yt_monitor.media.merge as video_merger
from src.yt_monitor.media.merge import (
    MergeJobManager,
    build_concat_demuxer_command,
    build_reencode_command,
    list_video_files,
    write_concat_list,
)


def test_list_video_files_filters_supported_extensions_and_sorts_newest_first(
    tmp_path: Path,
):
    root = tmp_path / "downloads"
    root.mkdir()
    older = root / "nested" / "older.MP4"
    older.parent.mkdir()
    older.write_bytes(b"old")
    newer = root / "newer.mkv"
    newer.write_bytes(b"newer")
    (root / "notes.txt").write_text("ignore", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    files = list_video_files(root)

    assert [(item.path, item.size_bytes, item.mtime) for item in files] == [
        ("newer.mkv", 5, 200.0),
        ("nested/older.MP4", 3, 100.0),
    ]


def test_write_concat_list_escapes_apostrophes_and_uses_absolute_paths(
    tmp_path: Path,
):
    first = tmp_path / "first.mp4"
    quoted = tmp_path / "owner's second.mp4"
    list_path = tmp_path / "concat.txt"

    write_concat_list([first, quoted], list_path)

    expected = "\n".join(
        f"file '{str(path.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
        for path in (first, quoted)
    )
    assert list_path.read_text(encoding="utf-8") == expected + "\n"


def test_concat_command_uses_safe_demuxer_and_stream_copy(tmp_path: Path):
    list_path = tmp_path / "concat.txt"
    output = tmp_path / "merged.mp4"

    assert build_concat_demuxer_command(list_path, output) == [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output),
    ]


def test_reencode_command_maps_every_input_pair_in_requested_order(tmp_path: Path):
    inputs = [tmp_path / "first.mp4", tmp_path / "second.mkv"]
    output = tmp_path / "merged.mp4"

    command = build_reencode_command(inputs, output)

    assert command == [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(inputs[0]),
        "-i",
        str(inputs[1]),
        "-filter_complex",
        "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output),
    ]


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


@pytest.mark.parametrize(
    ("inputs", "message"),
    [([], "비어있습니다"), (["one.mp4"], "최소 2개")],
)
def test_merge_rejects_insufficient_inputs(
    tmp_path: Path, inputs: list[str], message: str
):
    root = tmp_path / "downloads"
    root.mkdir()

    with pytest.raises(ValueError, match=message):
        MergeJobManager(root).submit(inputs, "out.mp4", "concat")


def test_merge_rejects_missing_input_and_invalid_output_name(tmp_path: Path):
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "one.mp4").write_bytes(b"one")
    (root / "two.mp4").write_bytes(b"two")
    manager = MergeJobManager(root)

    with pytest.raises(ValueError, match="존재하지 않습니다"):
        manager.submit(["one.mp4", "missing.mp4"], "out.mp4", "concat")
    with pytest.raises(ValueError, match="출력 파일명"):
        manager.submit(["one.mp4", "two.mp4"], "../out.mp4", "concat")


class _FinishedProcess:
    def __init__(self, returncode: int, lines: list[str]):
        self.returncode = returncode
        self.stdout = iter(lines)

    def wait(self) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def _submitted_job(tmp_path: Path, process: _FinishedProcess):
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "one.mp4").write_bytes(b"one")
    (root / "two.mp4").write_bytes(b"two")
    manager = MergeJobManager(root)
    with (
        patch.object(video_merger.threading, "Thread") as thread_class,
        patch.object(video_merger.subprocess, "Popen", return_value=process) as popen,
    ):
        job = manager.submit(["one.mp4", "two.mp4"], "out", "concat")
        target = thread_class.call_args.kwargs["target"]
        args = thread_class.call_args.kwargs["args"]
        yield root, manager, job, target, args, popen


def test_merge_job_success_updates_status_and_removes_concat_list(tmp_path: Path):
    process = _FinishedProcess(0, ["frame=1\n"])
    for root, manager, job, target, args, popen in _submitted_job(tmp_path, process):
        target(*args)

        completed = manager.get(job.id)
        assert completed is not None
        assert completed.status == "done"
        assert completed.message == "병합 완료"
        assert completed.output == "merged/out.mp4"
        assert not list((root / "merged").glob(".concat-*.txt"))
        command = popen.call_args.args[0]
        assert command[-2:] == ["copy", str(root / "merged" / "out.mp4")]


def test_merge_job_failure_keeps_only_recent_ffmpeg_error_tail(tmp_path: Path):
    process = _FinishedProcess(1, [f"line-{index}\n" for index in range(7)])
    for root, manager, job, target, args, _popen in _submitted_job(tmp_path, process):
        target(*args)

        failed = manager.get(job.id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.message == "\n".join(f"line-{index}" for index in range(2, 7))
        assert not list((root / "merged").glob(".concat-*.txt"))


def test_cancelled_queued_merge_never_starts_ffmpeg(tmp_path: Path):
    process = _FinishedProcess(0, [])
    for _root, manager, job, target, args, popen in _submitted_job(tmp_path, process):
        assert manager.cancel(job.id) is True
        target(*args)

        cancelled = manager.get(job.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.message == "사용자가 취소함"
        popen.assert_not_called()
