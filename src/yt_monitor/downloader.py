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
        self.download_directory = download_directory
        self.download_format = download_format
        self.logger = logger or logging.getLogger(__name__)
        self._setup_directory()

    def _setup_directory(self):
        Path(self.download_directory).mkdir(parents=True, exist_ok=True)

    def download(self, stream_url: str, filename_prefix: str = "stream") -> bool:
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'{filename_prefix}_{timestamp}.%(ext)s'
        return os.path.join(self.download_directory, filename)

    def _build_ydl_options(self, output_template: str) -> dict:
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])
