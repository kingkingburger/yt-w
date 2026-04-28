"""Internal DTO → dict 변환 — API 응답 직렬화에 쓰인다."""

from typing import Any, Dict

from ..channel_manager import ChannelDTO


def channel_to_dict(channel: ChannelDTO) -> Dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "url": channel.url,
        "enabled": channel.enabled,
        "download_format": channel.download_format,
    }


def cookie_validation_error_response(error: Exception) -> Dict[str, Any]:
    return {
        "valid": False,
        "message": f"검증 오류: {str(error)[:100]}",
        "checked_at": 0,
        "cached": False,
    }
