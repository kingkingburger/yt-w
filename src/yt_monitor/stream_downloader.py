"""Stream downloader — yt-dlp + ffmpeg으로 라이브 녹화 저장.

책임: yt-dlp로 스트림 정보 조회 + SplitStrategy에 따라 단일/세그먼트 다운로드.
분할 시간 계산, ffmpeg 커맨드 조립은 별도 모듈에서 (split_strategy, ffmpeg_command).
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yt_dlp

from .cookie_options import get_cookie_options
from .ffmpeg_command import build_ffmpeg_headers, build_segment_command
from .logger import Logger
from .split_strategy import NoSplit, make_split_strategy


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
            strategy = make_split_strategy(
                mode=self.split_mode,
                time_minutes=self.split_time_minutes,
                size_mb=self.split_size_mb,
            )

            if isinstance(strategy, NoSplit):
                output_file = os.path.join(
                    self.download_directory, f"{filename_prefix}_{timestamp}.mp4"
                )
                ydl_opts = self._build_ydl_options(output_file)
                self.logger.info(f"Starting download: {stream_url}")
                self._perform_download(stream_url, ydl_opts)
                self.logger.info("Download completed successfully")
                return True

            output_pattern = os.path.join(
                self.download_directory,
                f"{filename_prefix}_{timestamp}_part%03d.mp4",
            )
            self._download_with_realtime_split(stream_url, output_pattern)
            self.logger.info("All segments saved successfully")
            return True

        except Exception as error:
            self.logger.error(f"Download failed: {error}")
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
            **get_cookie_options(),
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
        }

    @staticmethod
    def _build_ffmpeg_headers(info: Dict[str, Any]) -> List[str]:
        """하위 호환: 이전 코드/테스트가 참조하는 정적 헬퍼."""
        return build_ffmpeg_headers(info)

    def _download_with_realtime_split(self, stream_url: str, output_pattern: str) -> None:
        strategy = make_split_strategy(
            mode=self.split_mode,
            time_minutes=self.split_time_minutes,
            size_mb=self.split_size_mb,
        )
        split_seconds = strategy.split_seconds()
        if split_seconds is None:
            raise ValueError(f"Invalid split_mode: {self.split_mode}")

        ydl_opts = {
            "format": self.download_format,
            "quiet": True,
            "live_from_start": False,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(stream_url, download=False)

        cmd = build_segment_command(info, output_pattern, split_seconds)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(
                f"FFmpeg failed (exit {result.returncode}): {result.stderr[-2000:]}"
            )
            raise Exception(
                f"FFmpeg segmented download failed (rc={result.returncode})"
            )

    def _perform_download(self, stream_url: str, ydl_opts: dict) -> None:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([stream_url])
