"""ffmpeg 기반 영상 병합 — 파일 스캔 + concat 커맨드 빌더 + 잡 매니저.

순수 함수(스캔/커맨드 빌드)와 부수효과(subprocess) 영역을 분리한다.
잡은 백그라운드 스레드에서 실행되며, _lock으로 _jobs/_processes를 보호한다.
"""

from __future__ import annotations

import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional


VideoExtensions = frozenset(
    {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".aac", ".ts", ".mov"}
)


@dataclass(frozen=True)
class FileInfoDTO:
    path: str
    name: str
    size_bytes: int
    mtime: float


@dataclass
class MergeJobDTO:
    id: str
    inputs: List[str]
    output: str
    mode: Literal["concat", "reencode"]
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    started_at: float
    finished_at: Optional[float]
    message: str
    elapsed_seconds: float


def list_video_files(root: Path) -> List[FileInfoDTO]:
    """root 하위의 영상 파일을 mtime 내림차순으로 반환한다."""
    if not root.exists():
        return []
    found: List[FileInfoDTO] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VideoExtensions:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        found.append(
            FileInfoDTO(
                path=path.relative_to(root).as_posix(),
                name=path.name,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            )
        )
    return sorted(found, key=lambda f: f.mtime, reverse=True)


def write_concat_list(absolute_files: List[Path], list_path: Path) -> None:
    """ffmpeg concat demuxer 입력 파일을 작성한다.

    single-quote 안의 single-quote는 '\\'' 시퀀스로 이스케이프한다.
    """
    lines: List[str] = []
    for path in absolute_files:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_concat_demuxer_command(list_file: Path, output: Path) -> List[str]:
    """stream-copy concat — 빠르지만 모든 입력의 코덱/해상도가 같아야 한다."""
    return [
        "ffmpeg", "-hide_banner", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output),
    ]


def build_reencode_command(input_files: List[Path], output: Path) -> List[str]:
    """filter_complex concat — 재인코딩으로 코덱/해상도가 달라도 병합 가능."""
    cmd: List[str] = ["ffmpeg", "-hide_banner", "-y"]
    for path in input_files:
        cmd.extend(["-i", str(path)])
    n = len(input_files)
    inputs_pairs = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    filter_str = f"{inputs_pairs}concat=n={n}:v=1:a=1[v][a]"
    cmd.extend([
        "-filter_complex", filter_str,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ])
    return cmd


class MergeJobManager:
    """병합 잡을 백그라운드 스레드로 실행하고 상태를 보관한다."""

    def __init__(self, root: Path, history_limit: int = 50):
        self._root: Path = root
        self._history_limit: int = history_limit
        self._jobs: Dict[str, MergeJobDTO] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._output_paths: Dict[str, Path] = {}
        self._lock: threading.Lock = threading.Lock()

    def set_root(self, root: Path) -> None:
        with self._lock:
            self._root = root

    def list_jobs(self) -> List[MergeJobDTO]:
        with self._lock:
            return sorted(
                self._jobs.values(), key=lambda j: j.started_at, reverse=True
            )

    def get(self, job_id: str) -> Optional[MergeJobDTO]:
        with self._lock:
            return self._jobs.get(job_id)

    def output_path(self, job_id: str) -> Optional[Path]:
        with self._lock:
            return self._output_paths.get(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            proc = self._processes.get(job_id)
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.status not in {"queued", "running"}:
                return False
            job.status = "cancelled"
            job.finished_at = time.time()
            job.message = "사용자가 취소함"
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        return True

    def submit(
        self,
        input_relative_paths: List[str],
        output_filename: str,
        mode: Literal["concat", "reencode"],
    ) -> MergeJobDTO:
        if not input_relative_paths:
            raise ValueError("입력 파일이 비어있습니다")
        if len(input_relative_paths) < 2:
            raise ValueError("병합하려면 최소 2개 파일이 필요합니다")

        with self._lock:
            root = self._root
        root_resolved = root.resolve()
        absolute_inputs: List[Path] = []
        for relative_path in input_relative_paths:
            full_path = (root / relative_path).resolve()
            try:
                full_path.relative_to(root_resolved)
            except ValueError:
                raise ValueError(f"잘못된 입력 경로: {relative_path}")
            if not full_path.is_file():
                raise ValueError(f"파일이 존재하지 않습니다: {relative_path}")
            absolute_inputs.append(full_path)

        if not output_filename or "/" in output_filename or "\\" in output_filename:
            raise ValueError("출력 파일명이 잘못되었습니다")
        if not output_filename.lower().endswith((".mp4", ".mkv")):
            output_filename = f"{output_filename}.mp4"

        output_dir = root / "merged"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / output_filename).resolve()

        job_id = uuid.uuid4().hex[:12]
        job = MergeJobDTO(
            id=job_id,
            inputs=input_relative_paths,
            output=output_path.relative_to(root_resolved).as_posix(),
            mode=mode,
            status="queued",
            started_at=time.time(),
            finished_at=None,
            message="시작 대기 중",
            elapsed_seconds=0.0,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._output_paths[job_id] = output_path
            self._evict_history_locked()
        threading.Thread(
            target=self._run,
            args=(job_id, absolute_inputs, output_path, mode),
            daemon=True,
        ).start()
        return job

    def _evict_history_locked(self) -> None:
        if len(self._jobs) <= self._history_limit:
            return
        finished = sorted(
            [j for j in self._jobs.values()
             if j.status in {"done", "failed", "cancelled"}],
            key=lambda j: j.finished_at or 0,
        )
        excess = len(self._jobs) - self._history_limit
        for old in finished[:excess]:
            self._jobs.pop(old.id, None)
            self._output_paths.pop(old.id, None)

    def _run(
        self,
        job_id: str,
        absolute_inputs: List[Path],
        output_path: Path,
        mode: Literal["concat", "reencode"],
    ) -> None:
        list_file: Optional[Path] = None
        try:
            with self._lock:
                job = self._jobs[job_id]
                if job.status == "cancelled":
                    return
                job.status = "running"
                job.message = "ffmpeg 실행 중"

            if mode == "concat":
                list_file = output_path.parent / f".concat-{job_id}.txt"
                write_concat_list(absolute_inputs, list_file)
                command = build_concat_demuxer_command(list_file, output_path)
            else:
                command = build_reencode_command(absolute_inputs, output_path)

            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            with self._lock:
                self._processes[job_id] = proc

            stderr_tail: List[str] = []
            assert proc.stdout is not None
            for line in proc.stdout:
                stripped = line.rstrip()
                stderr_tail.append(stripped)
                if len(stderr_tail) > 30:
                    stderr_tail.pop(0)
                with self._lock:
                    current = self._jobs[job_id]
                    current.elapsed_seconds = time.time() - current.started_at
                    if current.status == "cancelled":
                        break

            proc.wait()
            with self._lock:
                final = self._jobs[job_id]
                if final.status == "cancelled":
                    final.message = "취소됨"
                elif proc.returncode == 0:
                    final.status = "done"
                    final.message = "병합 완료"
                else:
                    final.status = "failed"
                    final.message = "\n".join(stderr_tail[-5:]) or "ffmpeg 실패"
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
            if list_file is not None and list_file.exists():
                try:
                    list_file.unlink()
                except OSError:
                    pass
