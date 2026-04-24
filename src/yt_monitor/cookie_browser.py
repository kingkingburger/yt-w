"""로컬 브라우저에서 yt-dlp를 경유해 쿠키를 추출한다.

Docker 환경에서는 브라우저가 없으므로 동작하지 않는다. 호출자는 결과의
success 필드로 실패를 판별하고, 필요하면 외부에서 알림을 보낸다.
"""

from typing import Any, Dict

from .cookie_options import _COOKIE_SOURCE_PATH, _TEST_VIDEO_URL


def extract_cookies_from_browser(browser: str = "firefox") -> Dict[str, Any]:
    """지정한 브라우저에서 쿠키를 추출해 cookies.txt에 저장한다."""
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "cookiesfrombrowser": (browser,),
            "cookiefile": _COOKIE_SOURCE_PATH,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(_TEST_VIDEO_URL, download=False)

        return {
            "success": True,
            "message": f"{browser}에서 쿠키 추출 완료",
            "browser": browser,
        }

    except Exception as error:
        error_text = str(error).lower()

        if "could not find" in error_text or "no browser" in error_text:
            message = (
                f"{browser} 브라우저를 찾을 수 없습니다. "
                "Docker 환경에서는 파일 업로드를 사용해주세요."
            )
        elif "permission" in error_text:
            message = (
                f"{browser} 쿠키 접근 권한이 없습니다. "
                "브라우저를 닫고 다시 시도해주세요."
            )
        else:
            message = f"쿠키 추출 실패: {str(error)[:150]}"

        return {
            "success": False,
            "message": message,
            "browser": browser,
        }
