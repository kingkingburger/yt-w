"""ffmpeg 기반 영상 분할 범위, 이름, 작업 등록 검증."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.yt_monitor.media.split import (
    SplitJobManager,
    build_split_command,
    build_split_ranges,
    probe_duration_seconds,
    split_output_paths,
)


def test_probe_duration_uses_ffprobe_contract_and_parses_seconds(tmp_path: Path):
    source = tmp_path / "video.mp4"
    result = subprocess.CompletedProcess([], 0, stdout="123.5\n", stderr="")

    with patch("src.yt_monitor.media.split.subprocess.run", return_value=result) as run:
        duration = probe_duration_seconds(source)

    assert duration == 123.5
    assert run.call_args.args[0] == [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(source),
    ]
    assert run.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            subprocess.CompletedProcess(
                [], 1, stdout="", stderr="first line\ninvalid media\n"
            ),
            "invalid media",
        ),
        (subprocess.CompletedProcess([], 0, stdout="not-a-number", stderr=""), "잘못된"),
        (subprocess.CompletedProcess([], 0, stdout="0", stderr=""), "0초"),
        (subprocess.CompletedProcess([], 0, stdout="nan", stderr=""), "0초"),
    ],
)
def test_probe_duration_rejects_process_and_value_failures(
    tmp_path: Path, result: subprocess.CompletedProcess[str], message: str
):
    with patch("src.yt_monitor.media.split.subprocess.run", return_value=result):
        with pytest.raises(ValueError, match=message):
            probe_duration_seconds(tmp_path / "video.mp4")


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("ffprobe", 30)])
def test_probe_duration_reports_ffprobe_execution_failure(
    tmp_path: Path, error: Exception
):
    with patch("src.yt_monitor.media.split.subprocess.run", side_effect=error):
        with pytest.raises(ValueError, match="ffprobe 실행 실패"):
            probe_duration_seconds(tmp_path / "video.mp4")


def test_build_interval_ranges_keeps_short_final_part():
    ranges = build_split_ranges(
        duration_seconds=13 * 3600,
        strategy="interval",
        interval_seconds=4 * 3600,
        parts=None,
    )

    assert [(item.start_seconds, item.duration_seconds) for item in ranges] == [
        (0, 4 * 3600),
        (4 * 3600, 4 * 3600),
        (8 * 3600, 4 * 3600),
        (12 * 3600, 3600),
    ]


def test_build_equal_ranges_returns_exact_requested_count():
    ranges = build_split_ranges(
        duration_seconds=13 * 3600,
        strategy="parts",
        interval_seconds=None,
        parts=3,
    )

    assert len(ranges) == 3
    assert ranges[0].start_seconds == 0
    assert ranges[1].start_seconds == pytest.approx(13 * 3600 / 3)
    assert sum(item.duration_seconds for item in ranges) == pytest.approx(13 * 3600)


def test_interval_must_create_at_least_two_files():
    with pytest.raises(ValueError, match="영상 길이보다 짧아야"):
        build_split_ranges(
            duration_seconds=3600,
            strategy="interval",
            interval_seconds=3600,
            parts=None,
        )


def test_split_output_names_keep_original_stem_and_extension(tmp_path: Path):
    source = tmp_path / "merged" / "recording.final.mp4"

    outputs = split_output_paths(source, tmp_path / "split", part_count=3)

    assert [path.name for path in outputs] == [
        "recording.final-1.mp4",
        "recording.final-2.mp4",
        "recording.final-3.mp4",
    ]


def test_split_command_uses_stream_copy_and_requested_range(tmp_path: Path):
    source = tmp_path / "input.mp4"
    output = tmp_path / "split" / "input-2.mp4"

    command = build_split_command(
        input_path=source,
        output_path=output,
        start_seconds=7200,
        duration_seconds=3600.5,
    )

    assert command == [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-ss",
        "7200.000",
        "-i",
        str(source),
        "-t",
        "3600.500",
        "-map",
        "0",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(output),
    ]


def test_submit_reserves_original_name_numbered_outputs(tmp_path: Path):
    root = tmp_path / "downloads"
    source = root / "merged" / "long-video.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video")

    with (
        patch(
            "src.yt_monitor.media.split.probe_duration_seconds",
            return_value=13 * 3600,
        ),
        patch("src.yt_monitor.media.split.threading.Thread") as thread_class,
    ):
        job = SplitJobManager(root).submit(
            input_relative_path="merged/long-video.mp4",
            strategy="parts",
            interval_seconds=None,
            parts=3,
        )

    assert job.input == "merged/long-video.mp4"
    assert job.outputs == [
        "split/long-video-1.mp4",
        "split/long-video-2.mp4",
        "split/long-video-3.mp4",
    ]
    assert job.total_parts == 3
    thread_class.assert_called_once()


def test_submit_supports_relative_download_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = Path("downloads")
    root.mkdir()
    (root / "long.mp4").write_bytes(b"video")

    with (
        patch(
            "src.yt_monitor.media.split.probe_duration_seconds",
            return_value=7200,
        ),
        patch("src.yt_monitor.media.split.threading.Thread"),
    ):
        job = SplitJobManager(root).submit(
            input_relative_path="long.mp4",
            strategy="parts",
            interval_seconds=None,
            parts=2,
        )

    assert job.outputs == ["split/long-1.mp4", "split/long-2.mp4"]


def test_submit_rejects_path_escape(tmp_path: Path):
    root = tmp_path / "downloads"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video")

    with pytest.raises(ValueError, match="잘못된 입력 경로"):
        SplitJobManager(root).submit(
            input_relative_path="../outside.mp4",
            strategy="parts",
            interval_seconds=None,
            parts=2,
        )


def test_submit_rejects_unsupported_input_and_existing_output(tmp_path: Path):
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "notes.txt").write_text("not video", encoding="utf-8")
    with pytest.raises(ValueError, match="지원하지 않는"):
        SplitJobManager(root).submit("notes.txt", "parts", None, 2)

    source = root / "video.mp4"
    source.write_bytes(b"video")
    output = root / "split" / "video-1.mp4"
    output.parent.mkdir()
    output.write_bytes(b"existing")
    with patch(
        "src.yt_monitor.media.split.probe_duration_seconds", return_value=120
    ):
        with pytest.raises(ValueError, match="이미 존재"):
            SplitJobManager(root).submit("video.mp4", "parts", None, 2)


def test_split_job_creates_each_numbered_file(tmp_path: Path):
    root = tmp_path / "downloads"
    source = root / "long.mp4"
    root.mkdir()
    source.write_bytes(b"video")
    manager = SplitJobManager(root)

    class FinishedProcess:
        returncode = 0
        stdout = iter(())

        def wait(self) -> int:
            return 0

        def poll(self) -> int:
            return 0

    with (
        patch(
            "src.yt_monitor.media.split.probe_duration_seconds",
            return_value=7200,
        ),
        patch("src.yt_monitor.media.split.subprocess.Popen") as popen,
        patch("src.yt_monitor.media.split.threading.Thread") as thread_class,
    ):
        popen.side_effect = lambda command, **kwargs: FinishedProcess()
        job = manager.submit(
            input_relative_path="long.mp4",
            strategy="parts",
            interval_seconds=None,
            parts=2,
        )
        target = thread_class.call_args.kwargs["target"]
        args = thread_class.call_args.kwargs["args"]
        target(*args)

    completed_job = manager.get(job.id)
    assert completed_job is not None
    assert completed_job.status == "done"
    assert completed_job.completed_parts == 2
    assert popen.call_count == 2


def test_cancelled_queued_split_never_starts_ffmpeg(tmp_path: Path):
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "video.mp4").write_bytes(b"video")
    manager = SplitJobManager(root)
    with (
        patch(
            "src.yt_monitor.media.split.probe_duration_seconds",
            return_value=120,
        ),
        patch("src.yt_monitor.media.split.threading.Thread") as thread_class,
        patch("src.yt_monitor.media.split.subprocess.Popen") as popen,
    ):
        job = manager.submit("video.mp4", "parts", None, 2)
        assert manager.cancel(job.id) is True
        thread_class.call_args.kwargs["target"](*thread_class.call_args.kwargs["args"])

    cancelled = manager.get(job.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.completed_parts == 0
    popen.assert_not_called()


def test_failed_split_removes_partial_outputs_and_releases_reservation(
    tmp_path: Path,
):
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "video.mp4").write_bytes(b"video")
    manager = SplitJobManager(root)

    class FailedProcess:
        returncode = 1
        stdout = iter(["ffmpeg detail\n"])

        def wait(self) -> int:
            return 1

        def poll(self) -> int:
            return 1

    def create_partial_output(command, **_kwargs):
        Path(command[-1]).write_bytes(b"partial")
        return FailedProcess()

    with (
        patch(
            "src.yt_monitor.media.split.probe_duration_seconds",
            return_value=120,
        ),
        patch("src.yt_monitor.media.split.threading.Thread") as thread_class,
        patch(
            "src.yt_monitor.media.split.subprocess.Popen",
            side_effect=create_partial_output,
        ),
    ):
        job = manager.submit("video.mp4", "parts", None, 2)
        thread_class.call_args.kwargs["target"](*thread_class.call_args.kwargs["args"])
        retry = manager.submit("video.mp4", "parts", None, 2)

    failed = manager.get(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert "ffmpeg detail" in failed.message
    assert all(not path.exists() for path in (root / "split").glob("video-*.mp4"))
    assert retry.id != job.id
