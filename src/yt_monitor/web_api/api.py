"""WebAPI 조립자 — FastAPI 앱 + 미들웨어 + 라우트 등록 + cleanup 스케줄러."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..channel_manager import ChannelManager
from ..logger import Logger
from .cleanup_scheduler import CleanupScheduler
from .routes import (
    register_channel_routes,
    register_cleanup_routes,
    register_cookie_routes,
    register_meta_routes,
    register_monitor_routes,
    register_video_routes,
)
from .state import MonitorState


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
        self.monitor_state = MonitorState()

        global_settings = self.channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)
        self.logger = Logger.get()

        self._register_routes()

        self.cleanup_scheduler = CleanupScheduler(channel_manager=self.channel_manager)
        self.cleanup_scheduler.start()

    # 하위 호환 속성 — 기존 코드/테스트가 self.monitor로 접근하는 경우
    @property
    def monitor(self):
        return self.monitor_state.monitor

    @monitor.setter
    def monitor(self, value):
        self.monitor_state.monitor = value

    @property
    def monitor_thread(self):
        return self.monitor_state.monitor_thread

    @monitor_thread.setter
    def monitor_thread(self, value):
        self.monitor_state.monitor_thread = value

    def _register_routes(self) -> None:
        register_meta_routes(self.app)
        register_channel_routes(self.app, self.channel_manager, self.monitor_state)
        register_monitor_routes(self.app, self.channel_manager, self.monitor_state)
        register_video_routes(self.app, self.channel_manager)
        register_cookie_routes(self.app)
        register_cleanup_routes(self.app, self.channel_manager)

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """개발용 서버 실행."""
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
