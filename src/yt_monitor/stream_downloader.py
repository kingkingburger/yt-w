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
        split_size_mb: int = 500,
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
                    self.download_directory, f"{filename_prefix}_{timestamp}.mp4"
                )
                ydl_opts = self._build_ydl_options(output_file)
                self.logger.info(f"Starting download: {stream_url}")
                self._perform_download(stream_url, ydl_opts)
                self.logger.info("Download completed successfully")
                return True

            output_pattern = os.path.join(
                self.download_directory, f"{filename_prefix}_{timestamp}_part%03d.mp4"
            )

            self._download_with_realtime_split(stream_url, output_pattern)
            self.logger.info("All segments saved successfully")
            return True

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False

    def _build_ydl_options(self, output_file: str) -> dict:
        return {
            "format": self.download_format,
            "outtmpl": output_file,
            "quiet": False,
            "no_warnings": False,
            "ignoreerrors": False,
            "live_from_start": False,
            "wait_for_video": (5, 20),
            "merge_output_format": "mp4",
            "cookiesfrombrowser": ("firefox",),
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
        }

    def _download_with_realtime_split(self, stream_url: str, output_pattern: str):
        # 분할 시간 계산
        if self.split_mode == "time":
            split_seconds = self.split_time_minutes * 60
        elif self.split_mode == "size":
            # 사이즈 기반 분할 시 예상 시간 계산
            estimated_bitrate_mbps = 5
            split_seconds = int((self.split_size_mb * 8) / estimated_bitrate_mbps)
        else:
            raise ValueError(f"Invalid split_mode: {self.split_mode}")

        ydl_opts = {
            "format": self.download_format,
            "quiet": True,
            "live_from_start": False,
            "cookiesfrombrowser": ("firefox",),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(stream_url, download=False)

        if "requested_formats" in info:
            # 비디오 + 오디오 분리된 경우
            video_url = info["requested_formats"][0]["url"]
            audio_url = info["requested_formats"][1]["url"]

            cmd = [
                "ffmpeg",
                "-i",
                video_url,
                "-i",
                audio_url,
                "-c",
                "copy",
                "-f",
                "segment",
                "-segment_time",
                str(split_seconds),
                "-reset_timestamps",
                "1",
                "-map",
                "0:v:0",  # 첫 번째 입력의 비디오 스트림 1개만
                "-map",
                "1:a:0",  # 두 번째 입력의 오디오 스트림 1개만
                output_pattern,
            ]
        else:
            # 단일 스트림
            direct_url = info["url"]
            cmd = [
                "ffmpeg",
                "-i",
                direct_url,
                "-c",
                "copy",
                "-f",
                "segment",
                "-map",
                "0:v:0",  # 비디오 1개만
                "-map",
                "0:a:0",  # 오디오 1개만
                "-segment_time",
                str(split_seconds),
                "-reset_timestamps",
                "1",
                output_pattern,
            ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise Exception("FFmpeg segmented download failed")

    def _perform_download(self, stream_url: str, ydl_opts: dict):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])
