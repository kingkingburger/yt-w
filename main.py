"""Web server entry point for YouTube Live Stream Monitor."""

import argparse
import os

from src.yt_monitor.web_api import WebAPI


def main():
    """Run the web server."""
    default_port = int(os.environ.get("YT_WEB_PORT", "8011"))

    parser = argparse.ArgumentParser(description="YouTube Live Monitor - Web Interface")

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help=f"Port to bind to (default: {default_port}, env: YT_WEB_PORT)",
    )

    parser.add_argument(
        "--channels",
        type=str,
        default="channels.json",
        help="Path to channels configuration file (default: channels.json)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("YouTube Live Monitor - Web Interface")
    print("=" * 60)
    print(f"Server starting at http://{args.host}:{args.port}")
    print(f"Channels file: {args.channels}")
    print()
    print("Open your browser and navigate to:")
    print(f"  http://localhost:{args.port}")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

    web_api = WebAPI(channels_file=args.channels)
    web_api.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
