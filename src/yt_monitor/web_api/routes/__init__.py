"""WebAPI 라우트 등록 함수 집합."""

from .channels import register_channel_routes
from .cleanup import register_cleanup_routes
from .cookies import register_cookie_routes
from .meta import register_meta_routes
from .monitor import register_monitor_routes
from .video import register_video_routes

__all__ = [
    "register_channel_routes",
    "register_cleanup_routes",
    "register_cookie_routes",
    "register_meta_routes",
    "register_monitor_routes",
    "register_video_routes",
]
