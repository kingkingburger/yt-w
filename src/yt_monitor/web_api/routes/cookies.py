"""/api/cookie/* 엔드포인트 — 검증/업로드/브라우저 추출."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from ...cookie_browser import extract_cookies_from_browser
from ...cookie_validator import invalidate_cookie_cache, validate_cookies
from ...discord_notifier import get_notifier
from ...logger import Logger
from ..dto_converters import cookie_validation_error_response


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
            return cookie_validation_error_response(error)

    @app.post("/api/cookie/refresh-check")
    async def refresh_cookie_check():
        try:
            invalidate_cookie_cache()
            result = await asyncio.to_thread(validate_cookies, True)
            if result["valid"]:
                logger.info("쿠키 갱신 확인됨 — 유효한 상태")
            else:
                logger.warning(f"쿠키 갱신 후에도 무효: {result['message']}")
                get_notifier().notify_cookie_expired(message=result["message"])
            return result
        except Exception as error:
            logger.error(f"Cookie refresh check error: {error}")
            return cookie_validation_error_response(error)

    @app.post("/api/cookie/upload")
    async def upload_cookies(file: UploadFile = File(...)):
        try:
            content = await file.read()
            text = content.decode("utf-8")

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

            cookie_path = Path("./cookies.txt")
            cookie_path.write_text(text, encoding="utf-8")
            logger.info(f"쿠키 파일 업로드됨: {len(cookie_lines)}개 쿠키 항목")

            invalidate_cookie_cache()
            result = await asyncio.to_thread(validate_cookies, True)

            if result["valid"]:
                logger.info("업로드된 쿠키 검증 성공")
            else:
                logger.warning(f"업로드된 쿠키 검증 실패: {result['message']}")

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
        except Exception as error:
            logger.error(f"Cookie upload error: {error}")
            raise HTTPException(status_code=500, detail=str(error))

    @app.post("/api/cookie/extract")
    async def extract_cookies(browser: str = "firefox"):
        try:
            logger.info(f"브라우저 쿠키 추출 시작: {browser}")
            result = await asyncio.to_thread(extract_cookies_from_browser, browser)

            if result["success"]:
                logger.info(f"쿠키 추출 성공: {browser}")
                validation = await asyncio.to_thread(validate_cookies, True)
                return {**result, **validation}

            logger.warning(f"쿠키 추출 실패: {result['message']}")
            return {**result, "valid": False}

        except Exception as error:
            logger.error(f"Cookie extract error: {error}")
            return {
                "success": False,
                "message": f"추출 오류: {str(error)[:100]}",
                "valid": False,
            }
