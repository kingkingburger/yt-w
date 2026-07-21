"""환경에 맞는 브라우저 쿠키와 yt-dlp 런타임 옵션을 구성한다."""

import os
from typing import Any, Dict, List


_REMOTE_COMPONENTS: List[str] = ["ejs:github"]
_TEST_VIDEO_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_POT_PROVIDER_URL: str = os.environ.get("YT_POT_PROVIDER_URL", "")
_DOCKER_FIREFOX_PROFILE: str = "/app/firefox_profile"


def _is_docker() -> bool:
    """Check if running inside a Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER") == "true"
    )


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
    Docker + 프로필 없음: 브라우저 쿠키 없이 실행
    Local: 시스템 브라우저 쿠키 사용 (기본 firefox)
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
        return base_options

    browser = os.environ.get("YT_COOKIE_BROWSER", "firefox")
    return {**base_options, "cookiesfrombrowser": (browser,)}
