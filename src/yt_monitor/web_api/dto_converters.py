"""Internal DTO → dict 변환 — API 응답 직렬화에 쓰인다."""

from typing import Any, Dict

from ..channel_manager import ChannelDTO, GlobalSettingsDTO


def channel_to_dict(channel: ChannelDTO) -> Dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "url": channel.url,
        "enabled": channel.enabled,
        "download_format": channel.download_format,
    }


def settings_to_dict(settings: GlobalSettingsDTO) -> Dict[str, Any]:
    return {
        "check_interval_seconds": settings.check_interval_seconds,
        "download_directory": settings.download_directory,
        "log_file": settings.log_file,
        "split_mode": settings.split_mode,
        "split_time_minutes": settings.split_time_minutes,
        "split_size_mb": settings.split_size_mb,
    }


def cookie_validation_error_response(error: Exception) -> Dict[str, Any]:
    return {
        "valid": False,
        "has_cookies": False,
        "message": f"검증 오류: {str(error)[:100]}",
        "checked_at": 0,
        "cached": False,
    }
