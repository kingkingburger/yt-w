"""Cookie and yt-dlp authentication helper."""

import os
import shutil
import tempfile
from typing import Dict, Any, List


_REMOTE_COMPONENTS: List[str] = ["ejs:github"]
_COOKIE_SOURCE_PATH: str = os.environ.get("YT_COOKIES_FILE", "./cookies.txt")
_cookie_temp_path: str = ""


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

    # Docker (Alpine): use nodejs instead of deno (deno requires glibc)
    if _is_docker():
        base_options["js_runtimes"] = {"node": {}}

    # Docker environment: use temp copy of cookies.txt (prevents overwrite)
    if _is_docker():
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
