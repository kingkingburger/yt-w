"""Runtime entry point for the web server."""

import os

from .app import WebAPI


def main() -> None:
    """Start the web server from container environment settings."""
    raw_port = os.environ.get("YT_WEB_PORT") or "8011"
    try:
        port = int(raw_port)
    except ValueError:
        raise SystemExit(f"Invalid YT_WEB_PORT: {raw_port!r}")

    host = "0.0.0.0"
    channels_file = "channels.json"

    print("=" * 60)
    print("YouTube Live Monitor - Web Interface")
    print("=" * 60)
    print(f"Server starting at http://{host}:{port}")
    print(f"Channels file: {channels_file}")
    print()
    print("Open your browser and navigate to:")
    print(f"  http://localhost:{port}")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

    web_api = WebAPI(channels_file=channels_file)
    web_api.run(host=host, port=port)


if __name__ == "__main__":
    main()
