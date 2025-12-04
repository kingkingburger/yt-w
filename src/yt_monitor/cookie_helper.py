"""Cookie helper for yt-dlp authentication."""

import os
from typing import Dict, Any


def get_cookie_options() -> Dict[str, Any]:
    """
    Get yt-dlp cookie options based on environment.

    In Docker: uses cookies.txt file (YT_COOKIES_FILE env or default path)
    In Windows/Local: uses Firefox browser cookies

    Returns:
        Dictionary with cookie options for yt-dlp
    """
    cookie_file_path = os.environ.get("YT_COOKIES_FILE", "/app/cookies.txt")

    # Check if running in Docker (cookie file exists) or local environment
    if os.path.exists(cookie_file_path):
        return {"cookiefile": cookie_file_path}

    # Fallback: try to use browser cookies (works on Windows/Mac/Linux with Firefox)
    return {"cookiesfrombrowser": ("firefox",)}
