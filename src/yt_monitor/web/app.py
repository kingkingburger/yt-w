"""WebAPI 조립자 — FastAPI 앱 + 미들웨어 + 라우트 등록 + cleanup 스케줄러."""

import os
import time
import tomllib
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..channels.repository import ChannelManager
from ..logging import Logger
from ..maintenance.scheduler import CleanupScheduler
from ..media.merge import MergeJobManager
from ..media.split import SplitJobManager
from ..youtube.upload import (
    GoogleYouTubeUploadRequestFactory,
    YouTubeOAuthManager,
    YouTubeUploadJobManager,
)
from .routes import (
    register_channel_routes,
    register_cookie_routes,
    register_merge_routes,
    register_meta_routes,
    register_monitor_routes,
    register_split_routes,
    register_system_routes,
    register_video_routes,
    register_youtube_upload_routes,
)

_PYPROJECT_PATH = Path(__file__).resolve().parents[3] / "pyproject.toml"
_APP_VERSION = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))["project"][
    "version"
]


class WebAPI:
    """YouTube Live Stream Monitor 용 Web API."""

    def __init__(self, channels_file: str = "channels.json"):
        """
        Args:
            channels_file: 채널 설정 파일 경로
        """
        self.app = FastAPI(title="YouTube Live Monitor", version=_APP_VERSION)
        allowed_hosts = [
            host.strip()
            for host in os.environ.get(
                "YT_WEB_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
            ).split(",")
            if host.strip()
        ]
        self.app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts,
        )

        self.channel_manager = ChannelManager(channels_file=channels_file)
        self.boot_time = time.time()

        global_settings = self.channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)
        self.logger = Logger.get()

        self.merge_job_manager = MergeJobManager(
            root=Path(global_settings.download_directory)
        )
        self.split_job_manager = SplitJobManager(
            root=Path(global_settings.download_directory)
        )
        self.youtube_oauth_manager = YouTubeOAuthManager.from_environment()
        self.youtube_upload_job_manager = YouTubeUploadJobManager(
            root=Path(global_settings.download_directory),
            request_factory=GoogleYouTubeUploadRequestFactory(
                self.youtube_oauth_manager
            ),
        )
        self.app.state.youtube_oauth_manager = self.youtube_oauth_manager
        self.app.state.youtube_upload_job_manager = self.youtube_upload_job_manager

        self._register_routes()

        self.cleanup_scheduler = CleanupScheduler(channel_manager=self.channel_manager)
        self.cleanup_scheduler.start()

    def _register_routes(self) -> None:
        register_meta_routes(self.app)
        register_channel_routes(self.app, self.channel_manager)
        register_monitor_routes(self.app, self.channel_manager)
        register_video_routes(self.app, self.channel_manager)
        register_cookie_routes(self.app)
        register_merge_routes(self.app, self.channel_manager, self.merge_job_manager)
        register_split_routes(self.app, self.channel_manager, self.split_job_manager)
        register_youtube_upload_routes(
            self.app,
            self.channel_manager,
            self.youtube_oauth_manager,
            self.youtube_upload_job_manager,
            self.merge_job_manager,
            self.split_job_manager,
        )
        register_system_routes(
            self.app,
            self.channel_manager,
            boot_time=self.boot_time,
        )

    def run(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """개발용 서버 실행."""
        import uvicorn

        # OAuth callback query에는 authorization code가 포함되므로 access log에서
        # 전체 URL을 남기지 않는다. 애플리케이션 로그는 민감하지 않은 결과만 기록한다.
        uvicorn.run(self.app, host=host, port=port, access_log=False)
