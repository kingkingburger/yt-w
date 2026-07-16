"""/api/files, /api/merge/* 엔드포인트 — 병합 워크스페이스."""

import asyncio
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ...channels.repository import ChannelManager
from ...logging import Logger
from ...media.merge import MergeJobManager, list_video_files
from ..schemas import MergeRequest

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
