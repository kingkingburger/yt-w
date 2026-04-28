"""/api/files, /api/merge/* 엔드포인트 — 병합 워크스페이스."""

from pathlib import Path
from typing import List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...channel_manager import ChannelManager
from ...logger import Logger
from ...video_merger import (
    MergeJobManager,
    file_info_to_dict,
    list_video_files,
    merge_job_to_dict,
)


class MergeRequest(BaseModel):
    inputs: List[str]
    output: str
    mode: Literal["concat", "reencode"] = "concat"


def register_merge_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    job_manager: MergeJobManager,
) -> None:
    logger = Logger.get()

    def _root() -> Path:
        return Path(channel_manager.get_global_settings().download_directory)

    @app.get("/api/files")
    async def list_files():
        return [file_info_to_dict(f) for f in list_video_files(_root())]

    @app.post("/api/merge")
    async def submit_merge(request: MergeRequest):
        try:
            job = job_manager.submit(
                input_relative_paths=request.inputs,
                output_filename=request.output,
                mode=request.mode,
            )
            logger.info(
                f"Merge job submitted: id={job.id} mode={job.mode} "
                f"inputs={len(job.inputs)} output={job.output}"
            )
            return merge_job_to_dict(job)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.get("/api/merge/jobs")
    async def list_jobs():
        return [merge_job_to_dict(j) for j in job_manager.list_jobs()]

    @app.get("/api/merge/jobs/{job_id}")
    async def get_job(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return merge_job_to_dict(job)

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
        path = _root() / job.output
        if not path.exists():
            raise HTTPException(status_code=404, detail="Merged file missing")
        return FileResponse(path=str(path), filename=path.name)
