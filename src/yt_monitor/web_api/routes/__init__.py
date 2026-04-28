"""WebAPI 라우트 등록 함수 집합."""

from .channels import register_channel_routes
from .cookies import register_cookie_routes
from .merge import register_merge_routes
from .meta import register_meta_routes
from .monitor import register_monitor_routes
from .system import register_system_routes
from .video import register_video_routes

__all__ = [
    "register_channel_routes",
    "register_cookie_routes",
    "register_merge_routes",
    "register_meta_routes",
    "register_monitor_routes",
    "register_system_routes",
    "register_video_routes",
]
