"""Main entry point for YouTube Live Stream Monitor."""

from src.yt_monitor import ConfigLoader, LiveStreamMonitor, Logger


def main():
    print("=" * 50)
    print("라이브 방송 모니터 & 다운로더")
    print("=" * 50)

    try:
        config = ConfigLoader.load("config.json")
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


if __name__ == "__main__":
    main()
