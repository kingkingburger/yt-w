"""ffmpeg 기반 영상 분할 — 범위 계산, 길이 확인, 백그라운드 작업 관리."""

from __future__ import annotations

import math
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set

from .merge import VideoExtensions


SplitStrategy = Literal["interval", "parts"]


@dataclass(frozen=True)
class SplitRangeDTO:
    index: int
    start_seconds: float
    duration_seconds: float


@dataclass
class SplitJobDTO:
    id: str
    input: str
    outputs: List[str]
    strategy: SplitStrategy
    interval_seconds: Optional[float]
    parts: Optional[int]
    duration_seconds: float
    total_parts: int
    completed_parts: int
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    started_at: float
    finished_at: Optional[float]
    message: str
    elapsed_seconds: float


def probe_duration_seconds(input_path: Path) -> float:
    """ffprobe로 미디어 전체 길이를 초 단위로 읽는다."""
    command: List[str] = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise ValueError("영상 길이를 확인할 수 없습니다: ffprobe 실행 실패") from error

    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        message = detail[-1] if detail else "ffprobe 실패"
        raise ValueError(f"영상 길이를 확인할 수 없습니다: {message}")
    try:
        duration_seconds = float(result.stdout.strip())
    except ValueError as error:
        raise ValueError("영상 길이를 확인할 수 없습니다: 잘못된 길이 값") from error
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("영상 길이를 확인할 수 없습니다: 길이가 0초입니다")
    return duration_seconds


def build_split_ranges(
    duration_seconds: float,
    strategy: SplitStrategy,
    interval_seconds: Optional[float],
    parts: Optional[int],
) -> List[SplitRangeDTO]:
    """시간 간격 또는 N등분 기준을 실제 시작점과 길이 목록으로 바꾼다."""
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("영상 길이는 0초보다 커야 합니다")

    if strategy == "interval":
        if interval_seconds is None or not math.isfinite(interval_seconds):
            raise ValueError("분할 간격을 입력해 주세요")
        if interval_seconds <= 0:
            raise ValueError("분할 간격은 0초보다 커야 합니다")
        if interval_seconds >= duration_seconds:
            raise ValueError("분할 간격은 영상 길이보다 짧아야 합니다")

        part_count = math.ceil((duration_seconds - 1e-6) / interval_seconds)
        ranges: List[SplitRangeDTO] = []
        for index in range(part_count):
            start_seconds = index * interval_seconds
            end_seconds = min(start_seconds + interval_seconds, duration_seconds)
            ranges.append(
                SplitRangeDTO(
                    index=index + 1,
                    start_seconds=start_seconds,
                    duration_seconds=end_seconds - start_seconds,
                )
            )
        return ranges

    if strategy == "parts":
        if parts is None:
            raise ValueError("몇 등분할지 입력해 주세요")
        if parts < 2:
            raise ValueError("2등분 이상을 선택해 주세요")
        if parts > math.floor(duration_seconds):
            raise ValueError("각 분할 파일은 최소 1초 이상이어야 합니다")

        equal_ranges: List[SplitRangeDTO] = []
        for index in range(parts):
            start_seconds = duration_seconds * index / parts
            end_seconds = duration_seconds * (index + 1) / parts
            equal_ranges.append(
                SplitRangeDTO(
                    index=index + 1,
                    start_seconds=start_seconds,
                    duration_seconds=end_seconds - start_seconds,
                )
            )
        return equal_ranges

    raise ValueError(f"지원하지 않는 분할 방식입니다: {strategy}")


def split_output_paths(
    input_path: Path,
    output_directory: Path,
    part_count: int,
) -> List[Path]:
    """원본 이름에 1부터 시작하는 번호 접미사를 붙인 출력 경로를 만든다."""
    return [
        output_directory / f"{input_path.stem}-{index}{input_path.suffix}"
        for index in range(1, part_count + 1)
    ]


def build_split_command(
    input_path: Path,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
) -> List[str]:
    """원본 스트림을 재인코딩하지 않고 지정 범위만 복사하는 명령을 만든다."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration_seconds:.3f}",
        "-map",
        "0",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(output_path),
    ]


class SplitJobManager:
    """영상 분할 작업을 백그라운드 스레드로 실행하고 상태를 보관한다."""

    def __init__(self, root: Path, history_limit: int = 50):
        self._root: Path = root
        self._history_limit: int = history_limit
        self._jobs: Dict[str, SplitJobDTO] = {}
        self._processes: Dict[str, subprocess.Popen[str]] = {}
        self._output_paths: Dict[str, List[Path]] = {}
        self._reserved_outputs: Set[Path] = set()
        self._lock: threading.Lock = threading.Lock()

    def set_root(self, root: Path) -> None:
        with self._lock:
            self._root = root

    def list_jobs(self) -> List[SplitJobDTO]:
        with self._lock:
            return sorted(
                self._jobs.values(), key=lambda job: job.started_at, reverse=True
            )

    def get(self, job_id: str) -> Optional[SplitJobDTO]:
        with self._lock:
            return self._jobs.get(job_id)

    def output_path(self, job_id: str, part_number: int) -> Optional[Path]:
        with self._lock:
            paths = self._output_paths.get(job_id)
            if paths is None or part_number < 1 or part_number > len(paths):
                return None
            return paths[part_number - 1]

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            process = self._processes.get(job_id)
            job = self._jobs.get(job_id)
            if job is None or job.status not in {"queued", "running"}:
                return False
            job.status = "cancelled"
            job.finished_at = time.time()
            job.message = "사용자가 취소함"
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        return True

    def submit(
        self,
        input_relative_path: str,
        strategy: SplitStrategy,
        interval_seconds: Optional[float],
        parts: Optional[int],
    ) -> SplitJobDTO:
        if strategy == "interval":
            if interval_seconds is None or not math.isfinite(interval_seconds):
                raise ValueError("분할 간격을 입력해 주세요")
            if interval_seconds <= 0:
                raise ValueError("분할 간격은 0초보다 커야 합니다")
        elif strategy == "parts":
            if parts is None:
                raise ValueError("몇 등분할지 입력해 주세요")
            if parts < 2:
                raise ValueError("2등분 이상을 선택해 주세요")

        with self._lock:
            root = self._root
        root_resolved = root.resolve()
        input_path = (root / input_relative_path).resolve()
        try:
            input_path.relative_to(root_resolved)
        except ValueError as error:
            raise ValueError(f"잘못된 입력 경로: {input_relative_path}") from error
        if not input_path.is_file():
            raise ValueError(f"파일이 존재하지 않습니다: {input_relative_path}")
        if input_path.suffix.lower() not in VideoExtensions:
            raise ValueError("지원하지 않는 영상 형식입니다")

        duration_seconds = probe_duration_seconds(input_path)
        ranges = build_split_ranges(
            duration_seconds=duration_seconds,
            strategy=strategy,
            interval_seconds=interval_seconds,
            parts=parts,
        )
        output_directory = (root / "split").resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        absolute_outputs = split_output_paths(
            input_path=input_path,
            output_directory=output_directory,
            part_count=len(ranges),
        )

        with self._lock:
            collisions = [
                path
                for path in absolute_outputs
                if path.exists() or path in self._reserved_outputs
            ]
            if collisions:
                raise ValueError(f"출력 파일이 이미 존재합니다: {collisions[0].name}")
            self._reserved_outputs.update(absolute_outputs)

        job_id = uuid.uuid4().hex[:12]
        relative_outputs = [
            path.relative_to(root_resolved).as_posix() for path in absolute_outputs
        ]
        job = SplitJobDTO(
            id=job_id,
            input=input_relative_path,
            outputs=relative_outputs,
            strategy=strategy,
            interval_seconds=interval_seconds,
            parts=parts,
            duration_seconds=duration_seconds,
            total_parts=len(ranges),
            completed_parts=0,
            status="queued",
            started_at=time.time(),
            finished_at=None,
            message="시작 대기 중",
            elapsed_seconds=0.0,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._output_paths[job_id] = absolute_outputs
            self._evict_history_locked()
        threading.Thread(
            target=self._run,
            args=(job_id, input_path, ranges, absolute_outputs),
            daemon=True,
        ).start()
        return job

    def _evict_history_locked(self) -> None:
        if len(self._jobs) <= self._history_limit:
            return
        finished = sorted(
            [
                job
                for job in self._jobs.values()
                if job.status in {"done", "failed", "cancelled"}
            ],
            key=lambda job: job.finished_at or 0,
        )
        excess = len(self._jobs) - self._history_limit
        for old in finished[:excess]:
            self._jobs.pop(old.id, None)
            self._output_paths.pop(old.id, None)

    def _run(
        self,
        job_id: str,
        input_path: Path,
        ranges: List[SplitRangeDTO],
        output_paths: List[Path],
    ) -> None:
        stderr_tail: List[str] = []
        try:
            with self._lock:
                job = self._jobs[job_id]
                if job.status != "cancelled":
                    job.status = "running"

            for split_range, output_path in zip(ranges, output_paths):
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status == "cancelled":
                        break
                    current.message = (
                        f"{split_range.index}/{current.total_parts} 분할 중"
                    )

                command = build_split_command(
                    input_path=input_path,
                    output_path=output_path,
                    start_seconds=split_range.start_seconds,
                    duration_seconds=split_range.duration_seconds,
                )
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                with self._lock:
                    self._processes[job_id] = process

                stderr_tail = []
                assert process.stdout is not None
                for line in process.stdout:
                    stripped = line.rstrip()
                    stderr_tail.append(stripped)
                    if len(stderr_tail) > 30:
                        stderr_tail.pop(0)
                    with self._lock:
                        current = self._jobs[job_id]
                        current.elapsed_seconds = time.time() - current.started_at
                        if current.status == "cancelled":
                            break

                process.wait()
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status == "cancelled":
                        break
                    if process.returncode != 0:
                        message = "\n".join(stderr_tail[-5:]) or "ffmpeg 실패"
                        raise RuntimeError(message)
                    current.completed_parts = split_range.index

            with self._lock:
                final = self._jobs[job_id]
                if final.status == "cancelled":
                    final.message = "취소됨"
                else:
                    final.status = "done"
                    final.message = f"{final.total_parts}개 파일 분할 완료"
                    final.finished_at = time.time()
                if final.finished_at is None:
                    final.finished_at = time.time()
                final.elapsed_seconds = final.finished_at - final.started_at
        except Exception as error:
            with self._lock:
                failed = self._jobs[job_id]
                failed.status = "failed"
                failed.message = f"오류: {error}"
                failed.finished_at = time.time()
                failed.elapsed_seconds = failed.finished_at - failed.started_at
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
                final_status = self._jobs[job_id].status
                self._reserved_outputs.difference_update(output_paths)
            if final_status in {"failed", "cancelled"}:
                for output_path in output_paths:
                    try:
                        output_path.unlink(missing_ok=True)
                    except OSError:
                        pass
