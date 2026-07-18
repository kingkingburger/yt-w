"""YouTube URL normalization contracts."""

import pytest

from src.yt_monitor.youtube.url import sanitize_youtube_url


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "https://www.youtube.com/watch?v=abc&list=PL123&index=2&t=30s",
            "https://www.youtube.com/watch?v=abc&t=30s",
        ),
        (
            "https://youtu.be/abc?start_radio=1&rv=other&si=token#chapter",
            "https://youtu.be/abc?si=token#chapter",
        ),
        (
            "https://www.youtube.com/watch?v=abc&tag=one&tag=two",
            "https://www.youtube.com/watch?v=abc&tag=one&tag=two",
        ),
        ("https://www.youtube.com/@Channel", "https://www.youtube.com/@Channel"),
    ],
)
def test_sanitize_youtube_url_removes_only_playlist_context(
    raw_url: str, expected: str
):
    assert sanitize_youtube_url(raw_url) == expected
