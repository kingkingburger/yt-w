"""YouTube OAuth와 비공개 업로드 작업 API."""

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from ...channels.repository import ChannelManager
from ...logging import Logger
from ...media.merge import MergeJobManager
from ...media.split import SplitJobManager
from ...youtube.upload import (
    OAuthConfigurationError,
    OAuthConnectionError,
    OAuthStateError,
    YouTubeOAuthManager,
    YouTubeUploadJobManager,
    YouTubeUploadMetadataDTO,
)
from ..schemas import YouTubeUploadRequest

OAUTH_STATE_COOKIE_NAME: str = "yt_youtube_oauth_state"
WRITE_REQUEST_HEADER_NAME: str = "X-YT-Monitor-Request"


def require_same_origin_write(
    request_marker: Optional[str] = Header(
        default=None,
        alias=WRITE_REQUEST_HEADER_NAME,
    ),
) -> None:
    """Force a CORS preflight for browser calls from any foreign origin."""
    if request_marker != "1":
        raise HTTPException(status_code=403, detail="허용되지 않은 쓰기 요청입니다")


def _oauth_result_redirect(result: str) -> RedirectResponse:
    response = RedirectResponse(
        url=f"/?youtube_oauth={result}#youtube-upload",
        status_code=303,
    )
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        path="/api/youtube/oauth/callback",
    )
    return response


def register_youtube_upload_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
    oauth_manager: YouTubeOAuthManager,
    job_manager: YouTubeUploadJobManager,
    merge_job_manager: Optional[MergeJobManager] = None,
    split_job_manager: Optional[SplitJobManager] = None,
) -> None:
    logger = Logger.get()

    def _root() -> Path:
        return Path(channel_manager.get_global_settings().download_directory)

    def _is_active_media_output(source: str) -> bool:
        if merge_job_manager is not None:
            for merge_job in merge_job_manager.list_jobs():
                if (
                    merge_job.status in {"queued", "running"}
                    and merge_job.output == source
                ):
                    return True
        if split_job_manager is not None:
            for split_job in split_job_manager.list_jobs():
                if (
                    split_job.status in {"queued", "running"}
                    and source in split_job.outputs
                ):
                    return True
        return False

    @app.get("/api/youtube/oauth/status")
    async def youtube_oauth_status():
        return asdict(oauth_manager.status())

    @app.post(
        "/api/youtube/oauth/start",
        dependencies=[Depends(require_same_origin_write)],
    )
    async def start_youtube_oauth(response: Response):
        try:
            authorization_url, state = oauth_manager.start_authorization()
        except OAuthConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except OAuthConnectionError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        response.set_cookie(
            key=OAUTH_STATE_COOKIE_NAME,
            value=state,
            max_age=int(oauth_manager.state_ttl_seconds),
            httponly=True,
            secure=urlsplit(oauth_manager.redirect_uri).scheme == "https",
            samesite="lax",
            path="/api/youtube/oauth/callback",
        )
        return {"authorization_url": authorization_url}

    @app.get("/api/youtube/oauth/callback")
    async def finish_youtube_oauth(
        request: Request,
        state: Optional[str] = None,
        code: Optional[str] = None,
        error: Optional[str] = None,
    ):
        cookie_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
        try:
            flow = oauth_manager.consume_state(state, cookie_state)
        except OAuthStateError:
            logger.warning("YouTube OAuth callback rejected: invalid state")
            return _oauth_result_redirect("invalid_state")

        if error:
            if error == "access_denied":
                logger.warning("YouTube OAuth callback denied by user")
                return _oauth_result_redirect("denied")
            logger.error("YouTube OAuth callback returned an error")
            return _oauth_result_redirect("error")

        try:
            await asyncio.to_thread(oauth_manager.finish_authorization, flow, code)
        except OAuthConnectionError:
            logger.error("YouTube OAuth token exchange failed")
            return _oauth_result_redirect("error")

        logger.info("YouTube OAuth connection stored")
        return _oauth_result_redirect("connected")

    @app.delete(
        "/api/youtube/oauth/connection",
        dependencies=[Depends(require_same_origin_write)],
    )
    async def disconnect_youtube_oauth():
        await asyncio.to_thread(oauth_manager.disconnect)
        logger.info("YouTube OAuth connection removed")
        return {"connected": False}

    @app.post(
        "/api/youtube/uploads",
        status_code=202,
        dependencies=[Depends(require_same_origin_write)],
    )
    async def submit_youtube_upload(request: YouTubeUploadRequest):
        if _is_active_media_output(request.source):
            raise HTTPException(
                status_code=409,
                detail="병합 또는 분할이 끝난 뒤 업로드해 주세요",
            )
        try:
            job_manager.set_root(_root())
            job = job_manager.submit(
                source=request.source,
                metadata=YouTubeUploadMetadataDTO(
                    title=request.title,
                    description=request.description,
                    tags=request.tags,
                    category_id=request.category_id,
                    made_for_kids=request.made_for_kids,
                ),
            )
        except OAuthConnectionError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(f"YouTube upload submitted: id={job.id} source={job.source}")
        return asdict(job)

    @app.get("/api/youtube/uploads")
    async def list_youtube_uploads():
        return [asdict(job) for job in job_manager.list_jobs()]

    @app.get("/api/youtube/uploads/{job_id}")
    async def get_youtube_upload(job_id: str):
        job = job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return asdict(job)

    @app.post(
        "/api/youtube/uploads/{job_id}/cancel",
        dependencies=[Depends(require_same_origin_write)],
    )
    async def cancel_youtube_upload(job_id: str):
        result = job_manager.cancel(job_id)
        if result == "not_found":
            raise HTTPException(status_code=404, detail="Job not found")
        if result == "not_cancellable":
            raise HTTPException(status_code=409, detail="Cannot cancel job")
        return {"cancel_requested": True}
