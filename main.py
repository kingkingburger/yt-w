import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import yt_dlp


class LiveStreamMonitor:
    def __init__(self, config_path="config.json"):
        """Initialize the live stream monitor with configuration."""
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.setup_directories()
        self.is_downloading = False

    def load_config(self, config_path):
        """Load configuration from JSON file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config['log_file'], encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_directories(self):
        """Create download directory if it doesn't exist."""
        Path(self.config['download_directory']).mkdir(parents=True, exist_ok=True)

    def check_if_live(self, channel_url):
        """Check if the channel is currently live streaming."""
        # Try multiple methods to detect live streams

        # Method 1: Check /live endpoint
        live_url = channel_url.rstrip('/') + '/live'
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(live_url, download=False)

                if info and info.get('is_live', False):
                    video_id = info.get('id')
                    self.logger.info(f"Live stream found via /live endpoint: {video_id}")
                    return True, f"https://www.youtube.com/watch?v={video_id}"
        except Exception as e:
            self.logger.debug(f"/live endpoint check failed: {e}")

        # Method 2: Check /streams tab with error handling
        streams_url = channel_url.rstrip('/') + '/streams'
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'ignoreerrors': True,  # Ignore member-only videos
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(streams_url, download=False)

                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry:
                            continue

                        # Skip if it's an error entry
                        if 'id' not in entry:
                            continue

                        # Check if it's live
                        if entry.get('is_live', False):
                            video_id = entry.get('id')
                            self.logger.info(f"Live stream found in /streams: {video_id}")
                            return True, f"https://www.youtube.com/watch?v={video_id}"
        except Exception as e:
            self.logger.debug(f"/streams tab check failed: {e}")

        # Method 3: Check main channel page
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'ignoreerrors': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)

                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry or 'id' not in entry:
                            continue

                        if entry.get('is_live', False):
                            video_id = entry.get('id')
                            self.logger.info(f"Live stream found on channel page: {video_id}")
                            return True, f"https://www.youtube.com/watch?v={video_id}"
        except Exception as e:
            self.logger.debug(f"Channel page check failed: {e}")

        return False, None

    def download_live_stream(self, stream_url):
        """Download the live stream."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_template = os.path.join(
            self.config['download_directory'],
            f'침착맨_라이브_{timestamp}.%(ext)s'
        )

        ydl_opts = {
            'format': self.config['download_format'],
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'live_from_start': True,  # Download from the start of the live stream
            'wait_for_video': (5, 20),  # Wait for video if it's starting
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }

        try:
            self.logger.info(f"Starting download of live stream: {stream_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([stream_url])
            self.logger.info("Download completed successfully!")
            return True
        except Exception as e:
            self.logger.error(f"Error downloading stream: {e}")
            return False

    def monitor(self):
        """Main monitoring loop."""
        self.logger.info("Starting live stream monitor for 침착맨 channel...")
        self.logger.info(f"Channel URL: {self.config['channel_url']}")
        self.logger.info(f"Check interval: {self.config['check_interval_seconds']} seconds")

        while True:
            try:
                if not self.is_downloading:
                    self.logger.info("Checking for live stream...")
                    is_live, stream_url = self.check_if_live(self.config['channel_url'])

                    if is_live:
                        self.logger.info(f"Live stream detected! URL: {stream_url}")
                        self.is_downloading = True

                        # If stream_url is just an ID, construct full URL
                        if stream_url and not stream_url.startswith('http'):
                            stream_url = f"https://www.youtube.com/watch?v={stream_url}"

                        success = self.download_live_stream(stream_url)

                        if success:
                            self.logger.info("Download finished. Resuming monitoring...")
                        else:
                            self.logger.warning("Download failed. Resuming monitoring...")

                        self.is_downloading = False
                    else:
                        self.logger.info("No live stream found. Waiting...")

                time.sleep(self.config['check_interval_seconds'])

            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitor loop: {e}")
                time.sleep(self.config['check_interval_seconds'])


def main():
    """Main entry point."""
    print("=" * 50)
    print("침착맨 라이브 방송 모니터 & 다운로더")
    print("=" * 50)

    try:
        monitor = LiveStreamMonitor()
        monitor.monitor()
    except FileNotFoundError:
        print("Error: config.json file not found!")
        print("Please create a config.json file with the required settings.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
