"""Cookie and yt-dlp authentication helper."""

import os
import shutil
import tempfile
import threading
import time
from typing import Dict, Any, List, Optional


from .discord_notifier import get_notifier

_REMOTE_COMPONENTS: List[str] = ["ejs:github"]
_COOKIE_SOURCE_PATH: str = os.environ.get("YT_COOKIES_FILE", "./cookies.txt")
_POT_PROVIDER_URL: str = os.environ.get("YT_POT_PROVIDER_URL", "")
_TEST_VIDEO_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_cookie_temp_path: str = ""

# Cookie validation cache
_cookie_valid: Optional[bool] = None
_cookie_checked_at: float = 0.0
_COOKIE_CHECK_INTERVAL: float = 300.0  # 5 minutes

# Thread safety for shared mutable state
_lock: threading.Lock = threading.Lock()


def _is_docker() -> bool:
    """Check if running inside a Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER") == "true"
    )


def _get_writable_cookie_path() -> str:
    """
    Copy the original cookies.txt to a temp file and return its path.

    yt-dlp overwrites the cookiefile on every request, which corrupts
    the original cookies when authentication fails. Using a temp copy
    preserves the original file.
    """
    global _cookie_temp_path

    with _lock:
        if not os.path.exists(_COOKIE_SOURCE_PATH):
            return ""

        # Reuse existing temp file if source hasn't changed
        if _cookie_temp_path and os.path.exists(_cookie_temp_path):
            source_mtime = os.path.getmtime(_COOKIE_SOURCE_PATH)
            temp_mtime = os.path.getmtime(_cookie_temp_path)
            if source_mtime <= temp_mtime:
                return _cookie_temp_path

        # Create fresh temp copy from original
        temp_fd, temp_path = tempfile.mkstemp(suffix="_cookies.txt")
        os.close(temp_fd)
        shutil.copy2(_COOKIE_SOURCE_PATH, temp_path)
        _cookie_temp_path = temp_path
        return temp_path


def get_cookie_options() -> Dict[str, Any]:
    """
    Get yt-dlp cookie and authentication options based on environment.

    In Docker: uses a writable temp copy of cookies.txt (preserves original)
    In Local: uses cookies.txt if present, otherwise browser cookies

    Environment variables:
        YT_COOKIES_FILE: Path to cookies.txt (default: ./cookies.txt)
        YT_COOKIE_BROWSER: Browser to extract cookies from (default: firefox)
            Supported: firefox, edge, brave, opera, safari
            Note: chrome/edge have DPAPI decryption issues on Windows

    Returns:
        Dictionary with cookie and JS runtime options for yt-dlp
    """
    base_options: Dict[str, Any] = {"remote_components": _REMOTE_COMPONENTS}
    is_docker = _is_docker()

    # Docker (Alpine): use nodejs instead of deno (deno requires glibc)
    if is_docker:
        base_options["js_runtimes"] = {"node": {}}

    # PO Token provider: bypass YouTube bot detection without cookies
    if _POT_PROVIDER_URL:
        base_options["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [_POT_PROVIDER_URL]},
        }

    # Docker environment: use temp copy of cookies.txt (prevents overwrite)
    if is_docker:
        writable_path = _get_writable_cookie_path()
        if writable_path:
            return {**base_options, "cookiefile": writable_path}
        return base_options

    # Local environment: prefer cookies.txt if available
    if os.path.exists(_COOKIE_SOURCE_PATH):
        return {**base_options, "cookiefile": _COOKIE_SOURCE_PATH}

    # Fallback: use browser cookies directly
    browser = os.environ.get("YT_COOKIE_BROWSER", "firefox")
    return {**base_options, "cookiesfrombrowser": (browser,)}


def validate_cookies(force: bool = False) -> Dict[str, Any]:
    """
    Validate YouTube cookies by making a lightweight extraction request.

    Uses a cached result for 5 minutes to avoid hammering YouTube.

    Args:
        force: If True, bypass the cache and check immediately

    Returns:
        Dictionary with 'valid' (bool), 'message' (str), and 'has_cookies' (bool)
    """
    global _cookie_valid, _cookie_checked_at

    # Return cached result if recent enough
    now = time.time()
    with _lock:
        if not force and _cookie_valid is not None:
            if (now - _cookie_checked_at) < _COOKIE_CHECK_INTERVAL:
                return {
                    "valid": _cookie_valid,
                    "has_cookies": os.path.exists(_COOKIE_SOURCE_PATH),
                    "message": "쿠키 유효" if _cookie_valid else "쿠키 만료됨 — 브라우저에서 다시 내보내세요",
                    "checked_at": _cookie_checked_at,
                    "cached": True,
                }

    # Check if cookies.txt exists at all
    if not os.path.exists(_COOKIE_SOURCE_PATH):
        with _lock:
            _cookie_valid = False
            _cookie_checked_at = now
        get_notifier().notify_cookie_expired(message="cookies.txt 파일이 없습니다")
        return {
            "valid": False,
            "has_cookies": False,
            "message": "cookies.txt 파일이 없습니다",
            "checked_at": now,
            "cached": False,
        }

    # Try a lightweight yt-dlp extraction to validate cookies
    try:
        import yt_dlp

        cookie_opts = get_cookie_options()
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "socket_timeout": 15,
            **cookie_opts,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(_TEST_VIDEO_URL, download=False)

        if info and info.get("title"):
            with _lock:
                _cookie_valid = True
                _cookie_checked_at = now
            return {
                "valid": True,
                "has_cookies": True,
                "message": "쿠키 유효",
                "checked_at": now,
                "cached": False,
            }

        with _lock:
            _cookie_valid = False
            _cookie_checked_at = now
        get_notifier().notify_cookie_expired(message="쿠키 만료됨 — 브라우저에서 다시 내보내세요")
        return {
            "valid": False,
            "has_cookies": True,
            "message": "쿠키 만료됨 — 브라우저에서 다시 내보내세요",
            "checked_at": now,
            "cached": False,
        }

    except Exception as error:
        error_message = str(error)
        with _lock:
            _cookie_valid = False
            _cookie_checked_at = now

        if "Sign in to confirm" in error_message or "cookies" in error_message.lower():
            message = "쿠키 만료됨 — 브라우저에서 다시 내보내세요"
        else:
            message = f"쿠키 검증 실패: {error_message[:100]}"

        get_notifier().notify_cookie_expired(message=message)
        return {
            "valid": False,
            "has_cookies": True,
            "message": message,
            "checked_at": now,
            "cached": False,
        }


def invalidate_cookie_cache() -> None:
    """Reset the cookie validation cache so the next check is fresh."""
    global _cookie_valid, _cookie_checked_at
    with _lock:
        _cookie_valid = None
        _cookie_checked_at = 0.0


def extract_cookies_from_browser(browser: str = "firefox") -> Dict[str, Any]:
    """
    Extract cookies from a local browser using yt-dlp and save to cookies.txt.

    This only works when running locally (not in Docker) because the browser
    must be installed on the same machine.

    Args:
        browser: Browser to extract from (firefox, chrome, edge, brave)

    Returns:
        Dictionary with 'success' (bool) and 'message' (str)
    """
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

        # Invalidate cache after fresh extraction
        invalidate_cookie_cache()

        return {
            "success": True,
            "message": f"{browser}에서 쿠키 추출 완료",
            "browser": browser,
        }

    except Exception as error:
        error_message = str(error)

        if "could not find" in error_message.lower() or "no browser" in error_message.lower():
            message = f"{browser} 브라우저를 찾을 수 없습니다. Docker 환경에서는 파일 업로드를 사용해주세요."
        elif "permission" in error_message.lower():
            message = f"{browser} 쿠키 접근 권한이 없습니다. 브라우저를 닫고 다시 시도해주세요."
        else:
            message = f"쿠키 추출 실패: {error_message[:150]}"

        return {
            "success": False,
            "message": message,
            "browser": browser,
        }
