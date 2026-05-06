"""WebAPI 조립자 — FastAPI 앱 + 미들웨어 + 라우트 등록 + cleanup 스케줄러."""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..channel_manager import ChannelManager
from ..logger import Logger
from ..video_merger import MergeJobManager
from .cleanup_scheduler import CleanupScheduler
from .routes import (
    register_channel_routes,
    register_cookie_routes,
    register_merge_routes,
    register_meta_routes,
    register_monitor_routes,
    register_system_routes,
    register_video_routes,
)


class WebAPI:
    """YouTube Live Stream Monitor 용 Web API."""

    def __init__(self, channels_file: str = "channels.json"):
        """
        Args:
            channels_file: 채널 설정 파일 경로
        """
        self.app = FastAPI(title="YouTube Live Monitor", version="1.0.0")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.channel_manager = ChannelManager(channels_file=channels_file)
        self.boot_time = time.time()

        global_settings = self.channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)
        self.logger = Logger.get()

        self.merge_job_manager = MergeJobManager(
            root=Path(global_settings.download_directory)
        )

        self._register_routes()

        self.cleanup_scheduler = CleanupScheduler(channel_manager=self.channel_manager)
        self.cleanup_scheduler.start()

    def _register_routes(self) -> None:
        register_meta_routes(self.app)
        register_channel_routes(self.app, self.channel_manager)
        register_monitor_routes(self.app, self.channel_manager)
        register_video_routes(self.app, self.channel_manager)
        register_cookie_routes(self.app)
        register_merge_routes(
            self.app, self.channel_manager, self.merge_job_manager
        )
        register_system_routes(
            self.app,
            self.channel_manager,
            boot_time=self.boot_time,
        )

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """개발용 서버 실행."""
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
