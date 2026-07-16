"""영상 분할 작업 등록, 조회, 취소, 다운로드 엔드포인트."""

import asyncio
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Set

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from ...channels.repository import ChannelManager
from ...logging import Logger
from ...media.merge import VideoExtensions
from ...media.split import SplitJobManager
from ..schemas import SplitRequest, SplitUploadResponse


def normalize_upload_filename(filename: Optional[str]) -> str:
    """브라우저가 보낸 경로를 제거하고 지원하는 미디어 파일명만 남긴다."""
    normalized = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not normalized or normalized in {".", ".."}:
        raise ValueError("업로드 파일명이 잘못되었습니다")
    if Path(normalized).suffix.lower() not in VideoExtensions:
        raise ValueError("지원하지 않는 영상 형식입니다")
    return normalized


def available_upload_path(
    upload_directory: Path,
    filename: str,
    reserved_paths: Set[Path],
) -> Path:
    """기존 파일과 진행 중 업로드를 덮어쓰지 않는 경로를 고른다."""
    original = Path(filename)
    candidate = upload_directory / original.name
    number = 2
    while candidate.exists() or candidate in reserved_paths:
        candidate = upload_directory / f"{original.stem}-{number}{original.suffix}"
        number += 1
    return candidate


def register_split_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    job_manager: SplitJobManager,
) -> None:
    logger = Logger.get()
    upload_path_lock = asyncio.Lock()
    reserved_upload_paths: Set[Path] = set()

    def _root() -> Path:
        return Path(channel_manager.get_global_settings().download_directory)

    @app.post("/api/split/upload", response_model=SplitUploadResponse)
    async def upload_split_video(request: Request, filename: str):
        target_path: Optional[Path] = None
        temporary_path: Optional[Path] = None
        try:
            safe_filename = normalize_upload_filename(filename)
            root_resolved = _root().resolve()
            upload_directory = (root_resolved / "uploads").resolve()
            upload_directory.mkdir(parents=True, exist_ok=True)
            async with upload_path_lock:
                target_path = available_upload_path(
                    upload_directory=upload_directory,
                    filename=safe_filename,
                    reserved_paths=reserved_upload_paths,
                )
                reserved_upload_paths.add(target_path)

            temporary_path = upload_directory / f".upload-{uuid.uuid4().hex}.part"
            size_bytes = 0
            async with await anyio.open_file(temporary_path, "wb") as output:
                async for chunk in request.stream():
                    if not chunk:
                        continue
                    await output.write(chunk)
                    size_bytes += len(chunk)
            if size_bytes == 0:
                raise ValueError("빈 파일은 업로드할 수 없습니다")
            temporary_path.replace(target_path)
            relative_path = target_path.relative_to(root_resolved).as_posix()
            logger.info(
                f"Split source uploaded: path={relative_path} size={size_bytes}"
            )
            return SplitUploadResponse(
                path=relative_path,
                name=target_path.name,
                size_bytes=size_bytes,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except OSError as error:
            raise HTTPException(
                status_code=500,
                detail="업로드 파일을 저장하지 못했습니다",
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            if target_path is not None:
                async with upload_path_lock:
                    reserved_upload_paths.discard(target_path)

    @app.post("/api/split")
    async def submit_split(request: SplitRequest):
        try:
            job_manager.set_root(_root())
            job = job_manager.submit(
                input_relative_path=request.input,
                strategy=request.strategy,
                interval_seconds=request.interval_seconds,
                parts=request.parts,
            )
            logger.info(
                f"Split job submitted: id={job.id} strategy={job.strategy} "
                f"input={job.input} outputs={len(job.outputs)}"
            )
            return asdict(job)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/split/jobs")
    async def list_split_jobs():
        return [asdict(job) for job in job_manager.list_jobs()]

    @app.get("/api/split/jobs/{job_id}")
    async def get_split_job(job_id: str):
        job = job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(job)

    @app.post("/api/split/jobs/{job_id}/cancel")
    async def cancel_split_job(job_id: str):
        if not job_manager.cancel(job_id):
            raise HTTPException(status_code=400, detail="Cannot cancel job")
        return {"cancelled": True}

    @app.get("/api/split/jobs/{job_id}/download/{part_number}")
    async def download_split_file(job_id: str, part_number: int):
        job = job_manager.get(job_id)
        if job is None or job.status != "done":
            raise HTTPException(status_code=404, detail="Job output not ready")
        path = job_manager.output_path(job_id, part_number)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="Split file missing")
        return FileResponse(path=str(path), filename=path.name)
