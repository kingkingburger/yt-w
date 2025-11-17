"""Main entry point for YouTube Live Stream Monitor and Video Downloader."""

import argparse
import sys

from src.yt_monitor import ConfigLoader, LiveStreamMonitor, Logger
from src.yt_monitor.video_downloader import VideoDownloader


def monitor_mode(config_file: str):
    """Run in live stream monitoring mode."""
    print("=" * 50)
    print("라이브 방송 모니터 & 다운로더")
    print("=" * 50)

    try:
        config = ConfigLoader.load(config_file)
        Logger.initialize(log_file=config.log_file)
        monitor = LiveStreamMonitor(config=config)
        monitor.start()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create a config.json file with the required settings.")
    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def download_mode(args):
    """Run in single video download mode."""
    print("=" * 50)
    print("YouTube 동영상 다운로더")
    print("=" * 50)

    try:
        downloader = VideoDownloader(
            output_dir=args.output or "./downloads",
            quality=args.quality,
            audio_only=args.audio_only,
        )

        success = downloader.download(args.url, filename=args.filename)

        if success:
            print("\n✅ 다운로드 완료!")
        else:
            print("\n❌ 다운로드 실패!")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 다운로드 오류: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="YouTube 라이브 모니터 & 동영상 다운로더",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 라이브 모니터링 모드 (기본)
  python main.py

  # 일반 동영상 다운로드
  python main.py --url "https://youtube.com/watch?v=VIDEO_ID"

  # 화질 선택 (720p)
  python main.py --url "URL" --quality 720

  # 오디오만 추출 (MP3)
  python main.py --url "URL" --audio-only

  # 저장 경로 지정
  python main.py --url "URL" --output "./my_videos"
        """,
    )

    parser.add_argument(
        "--url", "-u", type=str, help="다운로드할 YouTube 동영상 URL"
    )

    parser.add_argument(
        "--quality",
        "-q",
        type=str,
        default="best",
        choices=["2160", "1440", "1080", "720", "480", "360", "best"],
        help="동영상 화질 (기본: best)",
    )

    parser.add_argument(
        "--audio-only",
        "-a",
        action="store_true",
        help="오디오만 추출 (MP3)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="저장 디렉토리 (기본: ./downloads)",
    )

    parser.add_argument(
        "--filename", "-f", type=str, help="저장할 파일명 (확장자 제외)"
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.json",
        help="설정 파일 경로 (기본: config.json)",
    )

    args = parser.parse_args()

    # URL이 제공되면 다운로드 모드, 아니면 모니터링 모드
    if args.url:
        download_mode(args)
    else:
        monitor_mode(args.config)


if __name__ == "__main__":
    main()
