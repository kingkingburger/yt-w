"""/api/files, /api/merge/* 엔드포인트 — 병합 워크스페이스."""

import asyncio
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ...channels.repository import ChannelManager
from ...logging import Logger
from ...media.merge import MergeJobManager, VideoExtensions, list_video_files
from ..schemas import FileDeleteRequest, MergeRequest

FILE_LIST_CACHE_TTL_SECONDS = 5.0


def register_merge_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    job_manager: MergeJobManager,
) -> None:
    logger = Logger.get()
    file_cache = {
        "root": "",
        "expires_at": 0.0,
        "files": [],
    }
    file_cache_lock = asyncio.Lock()

    def _root() -> Path:
        return Path(channel_manager.get_global_settings().download_directory)

    @app.get("/api/files")
    async def list_files(refresh: bool = False):
        root = _root()
        root_key = str(root.resolve())

        # cache stampede 방지: lock으로 동시 cache miss 시 스캔이 1회만 실행되게.
        async with file_cache_lock:
            now = time.time()
            if (
                not refresh
                and file_cache["root"] == root_key
                and float(file_cache["expires_at"]) > now
            ):
                files = file_cache["files"]
            else:
                files = await asyncio.to_thread(list_video_files, root)
                file_cache.update(
                    {
                        "root": root_key,
                        "expires_at": now + FILE_LIST_CACHE_TTL_SECONDS,
                        "files": files,
                    }
                )
        return [asdict(f) for f in files]

    @app.delete("/api/files")
    async def delete_files(request: FileDeleteRequest):
        if not request.paths:
            raise HTTPException(status_code=400, detail="삭제할 파일이 없습니다")

        root_resolved = _root().resolve()
        relative_paths = list(dict.fromkeys(request.paths))
        targets = []
        for relative_path in relative_paths:
            if (
                not relative_path
                or Path(relative_path).suffix.lower() not in VideoExtensions
            ):
                raise HTTPException(status_code=400, detail="잘못된 영상 파일 경로입니다")

            target = (root_resolved / relative_path).resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"다운로드 폴더 밖의 파일은 삭제할 수 없습니다: {relative_path}",
                )
            if not target.is_file():
                raise HTTPException(
                    status_code=404,
                    detail=f"파일이 존재하지 않습니다: {relative_path}",
                )
            targets.append(target)

        try:
            for target in targets:
                await asyncio.to_thread(target.unlink)
        except OSError as error:
            logger.error(f"Source file delete error: {error}")
            raise HTTPException(
                status_code=409,
                detail="사용 중인 파일을 삭제하지 못했습니다. 목록을 새로고침해 주세요",
            ) from error
        finally:
            async with file_cache_lock:
                file_cache.update({"root": "", "expires_at": 0.0, "files": []})

        logger.info(f"Source files deleted: count={len(relative_paths)}")
        return {"deleted": relative_paths, "count": len(relative_paths)}

    @app.post("/api/merge")
    async def submit_merge(request: MergeRequest):
        try:
            job_manager.set_root(_root())
            job = job_manager.submit(
                input_relative_paths=request.inputs,
                output_filename=request.output,
                mode=request.mode,
            )
            logger.info(
                f"Merge job submitted: id={job.id} mode={job.mode} "
                f"inputs={len(job.inputs)} output={job.output}"
            )
            return asdict(job)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.get("/api/merge/jobs")
    async def list_jobs():
        return [asdict(j) for j in job_manager.list_jobs()]

    @app.get("/api/merge/jobs/{job_id}")
    async def get_job(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(job)

    @app.post("/api/merge/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        if not job_manager.cancel(job_id):
            raise HTTPException(status_code=400, detail="Cannot cancel job")
        return {"cancelled": True}

    @app.get("/api/merge/jobs/{job_id}/download")
    async def download_merged(job_id: str):
        job = job_manager.get(job_id)
        if not job or job.status != "done":
            raise HTTPException(status_code=404, detail="Job output not ready")
        path = job_manager.output_path(job_id) or (_root() / job.output)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Merged file missing")
        return FileResponse(path=str(path), filename=path.name)
