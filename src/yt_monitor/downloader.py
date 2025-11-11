"""Stream downloader module."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import yt_dlp

from .logger import Logger


class StreamDownloader:
    """Download live streams from YouTube."""

    def __init__(
        self,
        download_directory: str,
        download_format: str,
        split_mode: str = "time",
        split_time_minutes: int = 30,
        split_size_mb: int = 500
    ):
        self.download_directory = download_directory
        self.download_format = download_format
        self.split_mode = split_mode
        self.split_time_minutes = split_time_minutes
        self.split_size_mb = split_size_mb
        self.logger = Logger.get()
        self._setup_directory()

    def _setup_directory(self):
        Path(self.download_directory).mkdir(parents=True, exist_ok=True)

    def download(self, stream_url: str, filename_prefix: str = "stream") -> bool:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if self.split_mode == "none":
                output_file = os.path.join(
                    self.download_directory,
                    f'{filename_prefix}_{timestamp}.mp4'
                )
                ydl_opts = self._build_ydl_options(output_file)
                self.logger.info(f"Starting download: {stream_url}")
                self._perform_download(stream_url, ydl_opts)
                self.logger.info("Download completed successfully")
                return True

            output_pattern = os.path.join(
                self.download_directory,
                f'{filename_prefix}_{timestamp}_part%03d.mp4'
            )

            split_msg = (
                f"Splitting by {self.split_mode}: "
                f"{self.split_time_minutes} minutes" if self.split_mode == "time"
                else f"{self.split_size_mb} MB"
            )
            self.logger.info(f"Starting download with real-time splitting: {stream_url}")
            self.logger.info(split_msg)

            self._download_with_realtime_split(stream_url, output_pattern)
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
        if self.split_mode == "time":
            split_seconds = self.split_time_minutes * 60
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-c', 'copy',
                '-f', 'segment',
                '-segment_time', str(split_seconds),
                '-reset_timestamps', '1',
                output_pattern
            ]
        elif self.split_mode == "size":
            split_bytes = self.split_size_mb * 1024 * 1024
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-c', 'copy',
                '-f', 'segment',
                '-segment_size', str(split_bytes),
                '-reset_timestamps', '1',
                output_pattern
            ]
        else:
            raise ValueError(f"Invalid split_mode: {self.split_mode}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg split failed: {result.stderr}")

    def _perform_download(self, stream_url: str, ydl_opts: dict):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])

    def _download_with_realtime_split(self, stream_url: str, output_pattern: str):
        direct_url = self._get_direct_stream_url(stream_url)

        if self.split_mode == "time":
            split_seconds = self.split_time_minutes * 60
            cmd = [
                'ffmpeg',
                '-i', direct_url,
                '-c', 'copy',
                '-f', 'segment',
                '-segment_time', str(split_seconds),
                '-reset_timestamps', '1',
                '-live_start_index', '0',
                output_pattern
            ]
        elif self.split_mode == "size":
            split_bytes = self.split_size_mb * 1024 * 1024
            cmd = [
                'ffmpeg',
                '-i', direct_url,
                '-c', 'copy',
                '-f', 'segment',
                '-segment_size', str(split_bytes),
                '-reset_timestamps', '1',
                '-live_start_index', '0',
                output_pattern
            ]
        else:
            raise ValueError(f"Invalid split_mode: {self.split_mode}")

        result = subprocess.run(cmd, capture_output=False, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg download failed with return code: {result.returncode}")

    def _get_direct_stream_url(self, stream_url: str) -> str:
        ydl_opts = {
            'format': self.download_format,
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(stream_url, download=False)
            return info['url']
