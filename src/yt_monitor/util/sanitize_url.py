from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def sanitize_youtube_url(url: str) -> str:
    """
    Remove 'list' parameter and everything after it from YouTube URL.

    Args:
        url: YouTube URL (potentially with playlist parameters)

    Returns:
        Sanitized URL without playlist parameters

    Examples:
        >>> sanitize_youtube_url("https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID&index=1")
        "https://www.youtube.com/watch?v=VIDEO_ID"
    """
    parsed = urlparse(url)

    # Parse query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Remove 'list' parameter if exists
    if 'list' in query_params:
        del query_params['list']

    # Remove other playlist-related parameters
    for param in ['index', 'start_radio', 'rv']:
        if param in query_params:
            del query_params[param]

    # Rebuild query string (flatten single-item lists)
    clean_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
    new_query = urlencode(clean_params, doseq=True)

    # Rebuild URL
    clean_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    return clean_url
