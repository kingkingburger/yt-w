"""Stream downloader module."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import yt_dlp

from .logger import Logger


class StreamDownloader:
    """Download live streams from YouTube."""

    def __init__(self, download_directory: str, download_format: str):
        self.download_directory = download_directory
        self.download_format = download_format
        self.logger = Logger.get()
        self._setup_directory()

    def _setup_directory(self):
        Path(self.download_directory).mkdir(parents=True, exist_ok=True)

    def download(self, stream_url: str, filename_prefix: str = "stream") -> bool:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = os.path.join(self.download_directory, f'{filename_prefix}_{timestamp}_temp.mp4')

            ydl_opts = self._build_ydl_options(temp_file)

            self.logger.info(f"Starting download: {stream_url}")
            self._perform_download(stream_url, ydl_opts)

            self.logger.info("Download completed. Splitting into 30-minute segments...")
            output_pattern = os.path.join(
                self.download_directory,
                f'{filename_prefix}_{timestamp}_part%03d.mp4'
            )
            self._split_video(temp_file, output_pattern)

            if os.path.exists(temp_file):
                os.remove(temp_file)
                self.logger.info("Temporary file removed")

            self.logger.info("All segments saved successfully")
            return True

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False

    def _build_ydl_options(self, output_file: str) -> dict:
        return {
            'format': self.download_format,
            'outtmpl': output_file,
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

    def _split_video(self, input_file: str, output_pattern: str):
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', '1800',
            '-reset_timestamps', '1',
            output_pattern
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg split failed: {result.stderr}")

    def _perform_download(self, stream_url: str, ydl_opts: dict):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])
