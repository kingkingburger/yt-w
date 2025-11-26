"""Web server entry point for YouTube Live Stream Monitor."""

import argparse
from src.yt_monitor.web_api import WebAPI


def main():
    """Run the web server."""
    parser = argparse.ArgumentParser(
        description="YouTube Live Monitor - Web Interface"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
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
