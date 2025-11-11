"""Stream downloader module."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp


class StreamDownloader:
    """Download live streams from YouTube."""

    def __init__(
        self,
        download_directory: str,
        download_format: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize stream downloader.

        Args:
            download_directory: Directory to save downloaded streams
            download_format: yt-dlp format string
            logger: Logger instance for logging
        """
        self.download_directory = download_directory
        self.download_format = download_format
        self.logger = logger or logging.getLogger(__name__)

        self._setup_directory()

    def _setup_directory(self):
        """Create download directory if it doesn't exist."""
        Path(self.download_directory).mkdir(parents=True, exist_ok=True)

    def download(
        self,
        stream_url: str,
        filename_prefix: str = "stream"
    ) -> bool:
        """
        Download a live stream.

        Args:
            stream_url: URL of the stream to download
            filename_prefix: Prefix for the output filename

        Returns:
            True if download successful, False otherwise
        """
        try:
            output_template = self._generate_output_path(filename_prefix)
            ydl_opts = self._build_ydl_options(output_template)

            self.logger.info(f"Starting download: {stream_url}")
            self._perform_download(stream_url, ydl_opts)
            self.logger.info("Download completed successfully")

            return True

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False

    def _generate_output_path(self, filename_prefix: str) -> str:
        """
        Generate output file path with timestamp.

        Args:
            filename_prefix: Prefix for the filename

        Returns:
            Full path for output file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'{filename_prefix}_{timestamp}.%(ext)s'
        return os.path.join(self.download_directory, filename)

    def _build_ydl_options(self, output_template: str) -> dict:
        """
        Build yt-dlp options dictionary.

        Args:
            output_template: Output file path template

        Returns:
            Dictionary of yt-dlp options
        """
        return {
            'format': self.download_format,
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'live_from_start': True,
            'wait_for_video': (5, 20),
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }

    def _perform_download(self, stream_url: str, ydl_opts: dict):
        """
        Perform the actual download using yt-dlp.

        Args:
            stream_url: URL of the stream to download
            ydl_opts: yt-dlp options dictionary
        """
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])
