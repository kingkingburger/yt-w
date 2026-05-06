"""/api/video/*, /api/download, /api/download/file 엔드포인트."""

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ...channel_manager import ChannelManager
from ...logger import Logger
from ...util.sanitize_url import sanitize_youtube_url
from ...video_downloader import VideoDownloader
from ..schemas import VideoDownloadRequest


def register_video_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
) -> None:
    logger = Logger.get()

    @app.post("/api/video/info")
    async def get_video_info(request: VideoDownloadRequest):
        try:
            clean_url = sanitize_youtube_url(request.url)
            logger.info(f"Fetching video info for: {clean_url}")
            downloader = VideoDownloader()

            info = await asyncio.wait_for(
                asyncio.to_thread(downloader.get_video_info, clean_url),
                timeout=20.0,
            )

            logger.info(f"Video info retrieved: {info.get('title', 'Unknown')}")

            return {
                "success": True,
                "title": info.get("title", "Unknown"),
                "uploader": info.get("uploader", "Unknown"),
                "duration": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail", ""),
            }

        except asyncio.TimeoutError:
            logger.error("Timeout while fetching video info")
            raise HTTPException(
                status_code=408,
                detail="Request timeout - YouTube took too long to respond",
            )
        except Exception as error:
            logger.error(f"Get video info error: {error}")
            raise HTTPException(status_code=500, detail=str(error))

    @app.post("/api/download")
    async def download_video(request: VideoDownloadRequest):
        try:
            clean_url = sanitize_youtube_url(request.url)

            settings = channel_manager.get_global_settings()
            download_dir = Path(settings.download_directory) / "web_downloads"
            download_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if request.audio_only:
                filename = f"audio_{timestamp}"
                extension = "mp3"
            else:
                filename = f"video_{timestamp}"
                extension = "mp4"

            downloader = VideoDownloader(
                output_dir=str(download_dir),
                quality=request.quality,
                audio_only=request.audio_only,
            )

            success = await asyncio.to_thread(
                downloader.download, clean_url, filename=filename
            )

            if success:
                file_path = download_dir / f"{filename}.{extension}"
                return {
                    "success": True,
                    "message": "Download completed successfully",
                    "download_directory": str(download_dir),
                    "filename": f"{filename}.{extension}",
                    "file_path": str(file_path),
                }
            raise HTTPException(status_code=500, detail="Download failed")

        except HTTPException:
            raise
        except Exception as error:
            logger.error(f"Download error: {error}")
            raise HTTPException(status_code=500, detail=str(error))

    @app.get("/api/download/file/{filename}")
    async def download_file(filename: str):
        try:
            settings = channel_manager.get_global_settings()
            download_dir = (
                Path(settings.download_directory) / "web_downloads"
            ).resolve()
            file_path = (download_dir / filename).resolve()

            try:
                file_path.relative_to(download_dir)
            except ValueError:
                raise HTTPException(status_code=404, detail="File not found")

            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type="application/octet-stream",
            )

        except HTTPException:
            raise
        except Exception as error:
            logger.error(f"File download error: {error}")
            raise HTTPException(status_code=500, detail=str(error))
