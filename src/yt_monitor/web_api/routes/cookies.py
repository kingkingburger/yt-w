"""/api/cookie/* — 검증 전용 (Firefox profile 마운트 후 수동 추출/업로드 경로 제거됨)."""

import asyncio

from fastapi import FastAPI

from ...cookie_validator import validate_cookies
from ...discord_notifier import get_notifier
from ...logger import Logger


def register_cookie_routes(app: FastAPI) -> None:
    logger = Logger.get()

    @app.get("/api/cookie/status")
    async def get_cookie_status(force: bool = False):
        try:
            result = await asyncio.to_thread(validate_cookies, force)
            if not result["valid"] and not result.get("cached"):
                logger.warning(f"쿠키 상태: {result['message']}")
                get_notifier().notify_cookie_expired(message=result["message"])
            return result
        except Exception as error:
            logger.error(f"Cookie validation error: {error}")
            return {
                "valid": False,
                "message": f"검증 오류: {str(error)[:100]}",
                "checked_at": 0,
                "cached": False,
            }
