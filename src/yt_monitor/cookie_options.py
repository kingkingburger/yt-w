"""yt-dlp 쿠키/인증 옵션 빌더.

책임: 환경(Docker/Local)에 따라 yt-dlp에 전달할 cookie/js-runtime 옵션을 결정한다.
검증이나 알림 책임 없음 — 그건 cookie_validator.py가 맡는다.

우선순위:
1. Firefox 프로필 직접 읽기 (cookiesfrombrowser) — Docker에서 /app/firefox_profile,
   로컬에서는 시스템 기본 프로필. 사용자 브라우저의 최신 쿠키를 자동 사용하므로
   수동 추출 불필요.
2. cookies.txt 파일 — 레거시/보조 경로. 있으면 사용하되 없어도 무방.
"""

import os
import shutil
import tempfile
import threading
from typing import Any, Dict, List


_REMOTE_COMPONENTS: List[str] = ["ejs:github"]
_COOKIE_SOURCE_PATH: str = os.environ.get("YT_COOKIES_FILE", "./cookies.txt")
_TEST_VIDEO_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_POT_PROVIDER_URL: str = os.environ.get("YT_POT_PROVIDER_URL", "")
_DOCKER_FIREFOX_PROFILE: str = "/app/firefox_profile"
_cookie_temp_path: str = ""
_lock: threading.Lock = threading.Lock()


def _is_docker() -> bool:
    """Check if running inside a Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER") == "true"
    )


def _get_writable_cookie_path() -> str:
    """원본 cookies.txt를 임시 파일로 복사해 그 경로를 반환한다.

    yt-dlp는 매 요청마다 cookiefile을 덮어쓰기 때문에 원본을 임시본으로
    보호한다. 원본 mtime이 더 새로우면 임시본을 재생성한다.
    """
    global _cookie_temp_path

    with _lock:
        if not os.path.exists(_COOKIE_SOURCE_PATH):
            return ""

        if _cookie_temp_path and os.path.exists(_cookie_temp_path):
            source_mtime = os.path.getmtime(_COOKIE_SOURCE_PATH)
            temp_mtime = os.path.getmtime(_cookie_temp_path)
            if source_mtime <= temp_mtime:
                return _cookie_temp_path

        temp_fd, temp_path = tempfile.mkstemp(suffix="_cookies.txt")
        os.close(temp_fd)
        shutil.copy2(_COOKIE_SOURCE_PATH, temp_path)
        _cookie_temp_path = temp_path
        return temp_path


def _get_firefox_profile_path() -> str:
    """컨테이너/호스트에서 Firefox 프로필 경로를 찾아 반환. 없으면 빈 문자열."""
    if _is_docker():
        if os.path.isdir(_DOCKER_FIREFOX_PROFILE):
            return _DOCKER_FIREFOX_PROFILE
        return ""

    # 로컬 환경에서는 yt-dlp가 자동으로 기본 프로필을 찾게 한다 —
    # 여기서는 명시적 경로 반환 없이 상위 로직이 cookiesfrombrowser=("firefox",)를 사용.
    return ""


def get_cookie_options() -> Dict[str, Any]:
    """환경에 따라 yt-dlp에 전달할 cookie/인증 옵션을 반환한다.

    Docker + /app/firefox_profile 존재: Firefox 프로필 직접 읽기
    Docker + 프로필 없음 + cookies.txt 있음: 임시 복사본의 cookies.txt
    Local: cookies.txt가 있으면 그대로, 없으면 브라우저 쿠키 (기본 firefox)
    """
    base_options: Dict[str, Any] = {"remote_components": _REMOTE_COMPONENTS}
    is_docker = _is_docker()

    if is_docker:
        base_options["js_runtimes"] = {"node": {}}

    if _POT_PROVIDER_URL:
        base_options["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [_POT_PROVIDER_URL]},
        }

    if is_docker:
        firefox_profile = _get_firefox_profile_path()
        if firefox_profile:
            return {
                **base_options,
                "cookiesfrombrowser": ("firefox", firefox_profile, None, None),
            }
        writable_path = _get_writable_cookie_path()
        if writable_path:
            return {**base_options, "cookiefile": writable_path}
        return base_options

    if os.path.exists(_COOKIE_SOURCE_PATH):
        return {**base_options, "cookiefile": _COOKIE_SOURCE_PATH}

    browser = os.environ.get("YT_COOKIE_BROWSER", "firefox")
    return {**base_options, "cookiesfrombrowser": (browser,)}
