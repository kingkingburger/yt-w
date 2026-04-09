from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import time
from datetime import datetime
from pathlib import Path
import asyncio

from .channel_manager import ChannelManager, ChannelDTO, GlobalSettingsDTO
from .multi_channel_monitor import MultiChannelMonitor
from .util.sanitize_url import sanitize_youtube_url
from .video_downloader import VideoDownloader
from .file_cleaner import FileCleaner
from .cookie_helper import validate_cookies, invalidate_cookie_cache, extract_cookies_from_browser
from .logger import Logger


class ChannelCreateRequest(BaseModel):
    """Request model for creating a channel."""

    name: str
    url: str
    enabled: bool = True
    download_format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]"


class ChannelUpdateRequest(BaseModel):
    """Request model for updating a channel."""

    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    download_format: Optional[str] = None


class GlobalSettingsUpdateRequest(BaseModel):
    """Request model for updating global settings."""

    check_interval_seconds: Optional[int] = None
    download_directory: Optional[str] = None
    log_file: Optional[str] = None
    split_mode: Optional[str] = None
    split_time_minutes: Optional[int] = None
    split_size_mb: Optional[int] = None


class VideoDownloadRequest(BaseModel):
    """Request model for downloading a video."""

    url: str
    quality: str = "best"
    audio_only: bool = False


class MonitorStatus(BaseModel):
    """Monitor status response model."""

    is_running: bool
    active_channels: int
    total_channels: int


class CleanupRequest(BaseModel):
    """Request model for cleanup operation."""

    retention_days: int = 7
    dry_run: bool = False


def _channel_to_dict(channel: ChannelDTO) -> Dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "url": channel.url,
        "enabled": channel.enabled,
        "download_format": channel.download_format,
    }


def _settings_to_dict(settings: GlobalSettingsDTO) -> Dict[str, Any]:
    return {
        "check_interval_seconds": settings.check_interval_seconds,
        "download_directory": settings.download_directory,
        "log_file": settings.log_file,
        "split_mode": settings.split_mode,
        "split_time_minutes": settings.split_time_minutes,
        "split_size_mb": settings.split_size_mb,
    }


class WebAPI:
    """Web API for YouTube Live Stream Monitor."""

    def __init__(self, channels_file: str = "channels.json"):
        """
        Initialize Web API.

        Args:
            channels_file: Path to channels configuration file
        """
        self.app = FastAPI(title="YouTube Live Monitor", version="1.0.0")

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.channel_manager = ChannelManager(channels_file=channels_file)
        self.monitor: Optional[MultiChannelMonitor] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.cleanup_running = False

        # Initialize logger with global settings
        global_settings = self.channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)
        self.logger = Logger.get()

        # Setup routes
        self._setup_routes()

        # Start cleanup scheduler
        self._start_cleanup_scheduler()

    def _setup_routes(self):
        """Setup API routes."""

        @self.app.get("/health")
        async def health_check():
            """Docker healthcheck용 엔드포인트."""
            return {"status": "ok"}

        @self.app.get("/")
        async def root():
            """Serve the web interface."""
            html_file = Path(__file__).parent.parent.parent / "web" / "index.html"
            if html_file.exists():
                return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
            return {"message": "YouTube Live Monitor API"}

        @self.app.get("/api/channels", response_model=List[Dict[str, Any]])
        async def list_channels(enabled_only: bool = False):
            """Get list of all channels."""
            channels = self.channel_manager.list_channels(enabled_only=enabled_only)
            return [_channel_to_dict(ch) for ch in channels]

        @self.app.get("/api/channels/{channel_id}", response_model=Dict[str, Any])
        async def get_channel(channel_id: str):
            """Get a specific channel by ID."""
            channel = self.channel_manager.get_channel(channel_id)
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            return _channel_to_dict(channel)

        @self.app.post("/api/channels", response_model=Dict[str, Any])
        async def create_channel(channel: ChannelCreateRequest):
            """Create a new channel."""
            try:
                # Sanitize URL to remove playlist parameters
                clean_url = sanitize_youtube_url(channel.url)

                new_channel = self.channel_manager.add_channel(
                    name=channel.name,
                    url=clean_url,
                    enabled=channel.enabled,
                    download_format=channel.download_format,
                )

                # If monitor is running and channel is enabled, start monitoring it
                if self.monitor and self.monitor.is_running and new_channel.enabled:
                    self.monitor.add_channel_and_start_monitoring(new_channel)

                return _channel_to_dict(new_channel)

            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.patch("/api/channels/{channel_id}", response_model=Dict[str, Any])
        async def update_channel(channel_id: str, channel: ChannelUpdateRequest):
            """Update a channel."""
            # Sanitize URL if provided
            clean_url = sanitize_youtube_url(channel.url) if channel.url else None

            updated_channel = self.channel_manager.update_channel(
                channel_id=channel_id,
                name=channel.name,
                url=clean_url,
                enabled=channel.enabled,
                download_format=channel.download_format,
            )

            if not updated_channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            # If monitor is running, handle enable/disable
            if self.monitor and self.monitor.is_running:
                if channel.enabled is not None:
                    if channel.enabled:
                        self.monitor.add_channel_and_start_monitoring(updated_channel)
                    else:
                        self.monitor.remove_channel_and_stop_monitoring(channel_id)

            return _channel_to_dict(updated_channel)

        @self.app.delete("/api/channels/{channel_id}")
        async def delete_channel(channel_id: str):
            """Delete a channel."""
            # Stop monitoring if running
            if self.monitor and self.monitor.is_running:
                self.monitor.remove_channel_and_stop_monitoring(channel_id)

            success = self.channel_manager.remove_channel(channel_id)

            if not success:
                raise HTTPException(status_code=404, detail="Channel not found")

            return {"message": "Channel deleted successfully"}

        @self.app.get("/api/settings", response_model=Dict[str, Any])
        async def get_settings():
            """Get global settings."""
            settings = self.channel_manager.get_global_settings()
            return _settings_to_dict(settings)

        @self.app.patch("/api/settings", response_model=Dict[str, Any])
        async def update_settings(settings: GlobalSettingsUpdateRequest):
            """Update global settings."""
            try:
                updated_settings = self.channel_manager.update_global_settings(
                    **settings.model_dump(exclude_none=True)
                )

                return _settings_to_dict(updated_settings)

            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/api/monitor/status", response_model=MonitorStatus)
        async def get_monitor_status():
            """Get monitoring status."""
            is_running = self.monitor is not None and self.monitor.is_running
            total_channels = len(self.channel_manager.list_channels())
            active_channels = len(self.channel_manager.list_channels(enabled_only=True))

            return MonitorStatus(
                is_running=is_running,
                active_channels=active_channels,
                total_channels=total_channels,
            )

        @self.app.post("/api/monitor/start")
        async def start_monitor(background_tasks: BackgroundTasks):
            """Start monitoring."""
            if self.monitor and self.monitor.is_running:
                raise HTTPException(
                    status_code=400, detail="Monitor is already running"
                )

            channels = self.channel_manager.list_channels(enabled_only=True)
            if not channels:
                raise HTTPException(
                    status_code=400, detail="No enabled channels to monitor"
                )

            # Create and start monitor in background thread
            self.monitor = MultiChannelMonitor(channel_manager=self.channel_manager)

            def run_monitor():
                try:
                    self.monitor.start()
                except Exception as e:
                    self.logger.error(f"Monitor error: {e}")

            self.monitor_thread = threading.Thread(target=run_monitor, daemon=True)
            self.monitor_thread.start()

            return {"message": "Monitor started successfully"}

        @self.app.post("/api/monitor/stop")
        async def stop_monitor():
            """Stop monitoring."""
            if not self.monitor or not self.monitor.is_running:
                raise HTTPException(status_code=400, detail="Monitor is not running")

            self.monitor.stop()

            # Wait for thread to finish
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5.0)

            return {"message": "Monitor stopped successfully"}

        @self.app.post("/api/video/info")
        async def get_video_info(request: VideoDownloadRequest):
            """Get video information."""
            try:
                # Sanitize URL to remove playlist parameters
                clean_url = sanitize_youtube_url(request.url)
                self.logger.info(f"Fetching video info for: {clean_url}")
                downloader = VideoDownloader()

                # 20초 타임아웃 설정
                info = await asyncio.wait_for(
                    asyncio.to_thread(downloader.get_video_info, clean_url),
                    timeout=20.0,
                )

                self.logger.info(
                    f"Video info retrieved: {info.get('title', 'Unknown')}"
                )

                return {
                    "success": True,
                    "title": info.get("title", "Unknown"),
                    "uploader": info.get("uploader", "Unknown"),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "thumbnail": info.get("thumbnail", ""),
                }

            except asyncio.TimeoutError:
                self.logger.error("Timeout while fetching video info")
                raise HTTPException(
                    status_code=408,
                    detail="Request timeout - YouTube took too long to respond",
                )
            except Exception as e:
                self.logger.error(f"Get video info error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/download")
        async def download_video(request: VideoDownloadRequest):
            """Download a video."""
            try:
                # Sanitize URL to remove playlist parameters
                clean_url = sanitize_youtube_url(request.url)

                global_settings = self.channel_manager.get_global_settings()
                download_dir = (
                    Path(global_settings.download_directory) / "web_downloads"
                )
                download_dir.mkdir(parents=True, exist_ok=True)

                # Generate filename
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

                # Download in background
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
                else:
                    raise HTTPException(status_code=500, detail="Download failed")

            except Exception as e:
                self.logger.error(f"Download error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/download/file/{filename}")
        async def download_file(filename: str):
            """Serve downloaded file."""
            try:
                global_settings = self.channel_manager.get_global_settings()
                download_dir = (
                    Path(global_settings.download_directory) / "web_downloads"
                )
                file_path = download_dir / filename

                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="File not found")

                return FileResponse(
                    path=str(file_path),
                    filename=filename,
                    media_type="application/octet-stream",
                )

            except Exception as e:
                self.logger.error(f"File download error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/cookie/status")
        async def get_cookie_status(force: bool = False):
            """Check if YouTube cookies are valid."""
            try:
                result = await asyncio.to_thread(validate_cookies, force)
                if not result["valid"]:
                    self.logger.warning(f"쿠키 상태: {result['message']}")
                return result
            except Exception as e:
                self.logger.error(f"Cookie validation error: {e}")
                return {
                    "valid": False,
                    "has_cookies": False,
                    "message": f"검증 오류: {str(e)[:100]}",
                    "checked_at": 0,
                    "cached": False,
                }

        @self.app.post("/api/cookie/refresh-check")
        async def refresh_cookie_check():
            """Force re-check cookie validity (after user updates cookies.txt)."""
            try:
                invalidate_cookie_cache()
                result = await asyncio.to_thread(validate_cookies, True)
                if result["valid"]:
                    self.logger.info("쿠키 갱신 확인됨 — 유효한 상태")
                else:
                    self.logger.warning(f"쿠키 갱신 후에도 무효: {result['message']}")
                return result
            except Exception as e:
                self.logger.error(f"Cookie refresh check error: {e}")
                return {
                    "valid": False,
                    "has_cookies": False,
                    "message": f"검증 오류: {str(e)[:100]}",
                    "checked_at": 0,
                    "cached": False,
                }

        @self.app.post("/api/cookie/upload")
        async def upload_cookies(file: UploadFile = File(...)):
            """Upload a new cookies.txt file, replace existing, and validate."""
            try:
                content = await file.read()
                text = content.decode("utf-8")

                # Basic validation: check Netscape cookie format
                lines = text.strip().splitlines()
                cookie_lines = [
                    line for line in lines
                    if line.strip() and not line.startswith("#")
                ]
                if not cookie_lines:
                    raise HTTPException(
                        status_code=400,
                        detail="유효한 쿠키가 없습니다. Netscape 형식의 cookies.txt 파일을 업로드해주세요.",
                    )

                # Write to cookies.txt
                cookie_path = Path("./cookies.txt")
                cookie_path.write_text(text, encoding="utf-8")
                self.logger.info(
                    f"쿠키 파일 업로드됨: {len(cookie_lines)}개 쿠키 항목"
                )

                # Invalidate cache and validate
                invalidate_cookie_cache()
                result = await asyncio.to_thread(validate_cookies, True)

                if result["valid"]:
                    self.logger.info("업로드된 쿠키 검증 성공")
                else:
                    self.logger.warning(
                        f"업로드된 쿠키 검증 실패: {result['message']}"
                    )

                return {
                    "uploaded": True,
                    "cookie_count": len(cookie_lines),
                    **result,
                }

            except HTTPException:
                raise
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="파일을 읽을 수 없습니다. UTF-8 텍스트 파일이어야 합니다.",
                )
            except Exception as e:
                self.logger.error(f"Cookie upload error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/cookie/extract")
        async def extract_cookies(browser: str = "firefox"):
            """Extract cookies directly from a local browser."""
            try:
                self.logger.info(f"브라우저 쿠키 추출 시작: {browser}")
                result = await asyncio.to_thread(
                    extract_cookies_from_browser, browser
                )

                if result["success"]:
                    self.logger.info(f"쿠키 추출 성공: {browser}")
                    # Validate the extracted cookies
                    validation = await asyncio.to_thread(validate_cookies, True)
                    return {**result, **validation}
                else:
                    self.logger.warning(f"쿠키 추출 실패: {result['message']}")
                    return {**result, "valid": False}

            except Exception as e:
                self.logger.error(f"Cookie extract error: {e}")
                return {
                    "success": False,
                    "message": f"추출 오류: {str(e)[:100]}",
                    "valid": False,
                }

        @self.app.get("/api/cleanup/status")
        async def get_cleanup_status():
            """Get cleanup status and summary."""
            global_settings = self.channel_manager.get_global_settings()
            cleaner = FileCleaner(
                download_directory=global_settings.download_directory,
                retention_days=7,
            )
            summary = cleaner.get_cleanup_summary()

            return {
                "files_to_delete": summary["files_to_delete"],
                "total_size_mb": round(summary["total_size_mb"], 2),
                "retention_days": summary["retention_days"],
                "live_files_preserved": summary["live_files_preserved"],
                "live_size_mb": round(summary["live_size_mb"], 2),
            }

        @self.app.post("/api/cleanup")
        async def run_cleanup(request: CleanupRequest):
            """Run cleanup to delete old files."""
            try:
                global_settings = self.channel_manager.get_global_settings()
                cleaner = FileCleaner(
                    download_directory=global_settings.download_directory,
                    retention_days=request.retention_days,
                )

                summary = cleaner.get_cleanup_summary()

                if request.dry_run:
                    old_files = cleaner.find_old_files()
                    return {
                        "dry_run": True,
                        "files_to_delete": summary["files_to_delete"],
                        "total_size_mb": round(summary["total_size_mb"], 2),
                        "files": [
                            {"path": str(f[0]), "age_days": round(f[1], 1)}
                            for f in old_files
                        ],
                    }

                deleted = cleaner.cleanup(dry_run=False)

                return {
                    "dry_run": False,
                    "deleted_count": len(deleted),
                    "deleted_files": [str(f) for f in deleted],
                }

            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _start_cleanup_scheduler(self) -> None:
        """Start background cleanup scheduler (runs daily)."""
        def cleanup_loop():
            self.cleanup_running = True
            while self.cleanup_running:
                try:
                    global_settings = self.channel_manager.get_global_settings()
                    cleaner = FileCleaner(
                        download_directory=global_settings.download_directory,
                        retention_days=7,
                    )

                    summary = cleaner.get_cleanup_summary()
                    if summary["files_to_delete"] > 0:
                        self.logger.info(
                            f"자동 정리: {summary['files_to_delete']}개 파일 "
                            f"({summary['total_size_mb']:.2f} MB) 삭제 예정"
                        )
                        cleaner.cleanup(dry_run=False)

                except Exception as e:
                    self.logger.error(f"자동 정리 오류: {e}")

                # Sleep for 24 hours (check daily)
                for _ in range(24 * 60 * 60):
                    if not self.cleanup_running:
                        break
                    time.sleep(1)

        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        self.logger.info("파일 자동 정리 스케줄러 시작됨 (매일 실행)")

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Run the web server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
