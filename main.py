"""Main entry point for YouTube Live Stream Monitor and Video Downloader."""

import argparse
import sys

from src.yt_monitor import (
    Logger,
    VideoDownloader,
    ChannelManager,
    MultiChannelMonitor,
)


def monitor_mode(channels_file: str):
    """Run in multi-channel monitoring mode."""
    print("=" * 50)
    print("멀티 채널 라이브 방송 모니터")
    print("=" * 50)

    try:
        channel_manager = ChannelManager(channels_file=channels_file)
        channels = channel_manager.list_channels(enabled_only=True)

        if not channels:
            print("[경고] 활성화된 채널이 없습니다.")
            print(f"'{channels_file}' 파일에 채널을 추가하거나")
            print("다음 명령어를 사용하세요:")
            print(f"  python main.py --add-channel 'NAME' 'URL'")
            sys.exit(0)

        global_settings = channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)

        monitor = MultiChannelMonitor(channel_manager=channel_manager)
        monitor.start()

    except FileNotFoundError as e:
        print(f"Error: {e}")
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
            print("\n[성공] 다운로드 완료!")
        else:
            print("\n[실패] 다운로드 실패!")
            sys.exit(1)

    except Exception as e:
        print(f"[오류] 다운로드 오류: {e}")
        sys.exit(1)


def add_channel_mode(args):
    """Add a new channel to monitor."""
    try:
        channel_manager = ChannelManager(channels_file=args.channels)

        channel = channel_manager.add_channel(
            name=args.name,
            url=args.channel_url,
            enabled=True,
        )

        print("[성공] 채널이 추가되었습니다!")
        print(f"  ID: {channel.id}")
        print(f"  이름: {channel.name}")
        print(f"  URL: {channel.url}")
        print(f"  활성화: {channel.enabled}")

    except ValueError as e:
        print(f"[오류] {e}")
        sys.exit(1)


def remove_channel_mode(args):
    """Remove a channel from monitoring."""
    try:
        channel_manager = ChannelManager(channels_file=args.channels)

        success = channel_manager.remove_channel(args.channel_id)

        if success:
            print(f"[성공] 채널 ID '{args.channel_id}'이(가) 삭제되었습니다.")
        else:
            print(f"[실패] 채널 ID '{args.channel_id}'을(를) 찾을 수 없습니다.")
            sys.exit(1)

    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)


def list_channels_mode(args):
    """List all channels."""
    try:
        channel_manager = ChannelManager(channels_file=args.channels)
        channels = channel_manager.list_channels(enabled_only=False)

        if not channels:
            print("등록된 채널이 없습니다.")
            return

        print(f"\n등록된 채널 목록 ({len(channels)}개):")
        print("=" * 80)

        for channel in channels:
            status = "[활성화]" if channel.enabled else "[비활성화]"
            print(f"  {status} {channel.name}")
            print(f"    ID: {channel.id}")
            print(f"    URL: {channel.url}")
            print(f"    포맷: {channel.download_format}")
            print("-" * 80)

    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)


def enable_channel_mode(args):
    """Enable a channel for monitoring."""
    try:
        channel_manager = ChannelManager(channels_file=args.channels)

        channel = channel_manager.update_channel(
            channel_id=args.channel_id, enabled=True
        )

        if channel:
            print(f"[성공] 채널 '{channel.name}'이(가) 활성화되었습니다.")
        else:
            print(f"[실패] 채널 ID '{args.channel_id}'을(를) 찾을 수 없습니다.")
            sys.exit(1)

    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)


def disable_channel_mode(args):
    """Disable a channel from monitoring."""
    try:
        channel_manager = ChannelManager(channels_file=args.channels)

        channel = channel_manager.update_channel(
            channel_id=args.channel_id, enabled=False
        )

        if channel:
            print(f"[성공] 채널 '{channel.name}'이(가) 비활성화되었습니다.")
        else:
            print(f"[실패] 채널 ID '{args.channel_id}'을(를) 찾을 수 없습니다.")
            sys.exit(1)

    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="YouTube 라이브 모니터 & 동영상 다운로더",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:

  [멀티 채널 모니터링] (기본):
    python main.py

  [채널 관리]:
    python main.py --add-channel "침착맨" "https://www.youtube.com/@chimchakman_vod"
    python main.py --list-channels
    python main.py --enable-channel CHANNEL_ID
    python main.py --disable-channel CHANNEL_ID
    python main.py --remove-channel CHANNEL_ID

  [일반 동영상 다운로드]:
    python main.py --url "https://youtube.com/watch?v=VIDEO_ID"
    python main.py --url "URL" --quality 720
    python main.py --url "URL" --audio-only
        """,
    )

    # Channel management arguments
    parser.add_argument(
        "--channels",
        "-ch",
        type=str,
        default="channels.json",
        help="채널 설정 파일 경로 (기본: channels.json)",
    )

    parser.add_argument(
        "--add-channel",
        nargs=2,
        metavar=("NAME", "URL"),
        help="새 채널 추가 (이름과 URL)",
    )

    parser.add_argument(
        "--remove-channel",
        metavar="CHANNEL_ID",
        help="채널 삭제 (채널 ID)",
    )

    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="등록된 채널 목록 보기",
    )

    parser.add_argument(
        "--enable-channel",
        metavar="CHANNEL_ID",
        help="채널 활성화 (채널 ID)",
    )

    parser.add_argument(
        "--disable-channel",
        metavar="CHANNEL_ID",
        help="채널 비활성화 (채널 ID)",
    )

    # Video download arguments
    parser.add_argument("--url", "-u", type=str, help="다운로드할 YouTube 동영상 URL")

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

    args = parser.parse_args()

    # Determine which mode to run
    if args.add_channel:
        args.name, args.channel_url = args.add_channel
        add_channel_mode(args)

    elif args.remove_channel:
        args.channel_id = args.remove_channel
        remove_channel_mode(args)

    elif args.list_channels:
        list_channels_mode(args)

    elif args.enable_channel:
        args.channel_id = args.enable_channel
        enable_channel_mode(args)

    elif args.disable_channel:
        args.channel_id = args.disable_channel
        disable_channel_mode(args)

    elif args.url:
        download_mode(args)

    else:
        # Default: multi-channel monitoring mode
        monitor_mode(args.channels)


if __name__ == "__main__":
    main()
