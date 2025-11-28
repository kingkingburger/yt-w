from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
from pathlib import Path
import asyncio

from .channel_manager import ChannelManager
from .multi_channel_monitor import MultiChannelMonitor
from .util.sanitize_url import sanitize_youtube_url
from .video_downloader import VideoDownloader
from .file_cleaner import FileCleaner
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
            return [
                {
                    "id": ch.id,
                    "name": ch.name,
                    "url": ch.url,
                    "enabled": ch.enabled,
                    "download_format": ch.download_format,
                }
                for ch in channels
            ]

        @self.app.get("/api/channels/{channel_id}", response_model=Dict[str, Any])
        async def get_channel(channel_id: str):
            """Get a specific channel by ID."""
            channel = self.channel_manager.get_channel(channel_id)
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            return {
                "id": channel.id,
                "name": channel.name,
                "url": channel.url,
                "enabled": channel.enabled,
                "download_format": channel.download_format,
            }

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

                return {
                    "id": new_channel.id,
                    "name": new_channel.name,
                    "url": new_channel.url,
                    "enabled": new_channel.enabled,
                    "download_format": new_channel.download_format,
                }

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

            return {
                "id": updated_channel.id,
                "name": updated_channel.name,
                "url": updated_channel.url,
                "enabled": updated_channel.enabled,
                "download_format": updated_channel.download_format,
            }

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
            return {
                "check_interval_seconds": settings.check_interval_seconds,
                "download_directory": settings.download_directory,
                "log_file": settings.log_file,
                "split_mode": settings.split_mode,
                "split_time_minutes": settings.split_time_minutes,
                "split_size_mb": settings.split_size_mb,
            }

        @self.app.patch("/api/settings", response_model=Dict[str, Any])
        async def update_settings(settings: GlobalSettingsUpdateRequest):
            """Update global settings."""
            try:
                updated_settings = self.channel_manager.update_global_settings(
                    **settings.model_dump(exclude_none=True)
                )

                return {
                    "check_interval_seconds": updated_settings.check_interval_seconds,
                    "download_directory": updated_settings.download_directory,
                    "log_file": updated_settings.log_file,
                    "split_mode": updated_settings.split_mode,
                    "split_time_minutes": updated_settings.split_time_minutes,
                    "split_size_mb": updated_settings.split_size_mb,
                }

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
                from datetime import datetime

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
        import time

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

    def _stop_cleanup_scheduler(self) -> None:
        """Stop cleanup scheduler."""
        self.cleanup_running = False

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Run the web server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
