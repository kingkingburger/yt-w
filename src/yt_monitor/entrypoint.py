"""Runtime entry point for the YouTube live-stream monitor."""

from .channels.repository import ChannelManager
from .logging import Logger
from .monitoring.service import MultiChannelMonitor


def main() -> None:
    """Start the monitor daemon with the container's channels file."""
    channels_file = "channels.json"

    print("=" * 50)
    print("멀티 채널 라이브 방송 모니터")
    print("=" * 50)

    try:
        channel_manager = ChannelManager(channels_file=channels_file)
        channels = channel_manager.list_channels(enabled_only=True)

        if not channels:
            print("[경고] 활성화된 채널이 없습니다.")
            print("웹 UI에서 채널을 추가하거나 활성화하세요.")
            return

        global_settings = channel_manager.get_global_settings()
        Logger.initialize(log_file=global_settings.log_file)

        monitor = MultiChannelMonitor(channel_manager=channel_manager)
        monitor.start()

    except FileNotFoundError as error:
        print(f"Error: {error}")
    except ValueError as error:
        print(f"Configuration error: {error}")
    except Exception as error:
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    main()
