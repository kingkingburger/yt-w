"""Main entry point for YouTube Live Stream Monitor."""

from src.yt_monitor import ConfigLoader, LiveStreamMonitor, setup_logger


def main():
    print("=" * 50)
    print("침착맨 라이브 방송 모니터 & 다운로더")
    print("=" * 50)

    try:
        config = ConfigLoader.load("config.json")
        logger = setup_logger(log_file=config.log_file, logger_name="yt_monitor")
        monitor = LiveStreamMonitor(config=config, logger=logger)
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
