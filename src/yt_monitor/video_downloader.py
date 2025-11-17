"""General YouTube video downloader module."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp


class VideoDownloader:
    """Download regular YouTube videos (non-live)."""

    def __init__(
        self,
        output_dir: str = "./downloads",
        quality: str = "best",
        audio_only: bool = False,
    ):
        """
        Initialize VideoDownloader.

        Args:
            output_dir: Directory to save downloaded files
            quality: Video quality (2160, 1440, 1080, 720, 480, 360, or 'best')
            audio_only: If True, download only audio as MP3
        """
        self.output_dir = output_dir
        self.quality = quality
        self.audio_only = audio_only
        self._setup_directory()

    def _setup_directory(self):
        """Create output directory if it doesn't exist."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def _get_format_string(self) -> str:
        """
        Generate yt-dlp format string based on quality settings.

        Returns:
            Format string for yt-dlp
        """
        if self.audio_only:
            return "bestaudio/best"

        if self.quality == "best":
            return "bestvideo+bestaudio/best"

        # Specific quality (e.g., 720, 1080)
        height = self.quality
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

    def _build_ydl_options(self, output_path: str) -> dict:
        """
        Build yt-dlp options dictionary.

        Args:
            output_path: Output file path template

        Returns:
            Dictionary of yt-dlp options
        """
        opts = {
            "format": self._get_format_string(),
            "outtmpl": output_path,
            "quiet": False,
            "no_warnings": False,
            "ignoreerrors": False,
        }

        if self.audio_only:
            # Extract audio as MP3
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            # Merge video+audio to MP4
            opts["merge_output_format"] = "mp4"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ]

        return opts

    def download(self, url: str, filename: Optional[str] = None) -> bool:
        """
        Download a YouTube video.

        Args:
            url: YouTube video URL
            filename: Optional custom filename (without extension)

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Generate filename
            if filename:
                base_filename = filename
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_filename = f"video_{timestamp}"

            # Set extension based on mode
            if self.audio_only:
                output_path = os.path.join(self.output_dir, f"{base_filename}.mp3")
            else:
                output_path = os.path.join(self.output_dir, f"{base_filename}.mp4")

            # Build options
            ydl_opts = self._build_ydl_options(output_path)

            # Download
            print(f"\n📥 다운로드 시작...")
            print(f"   URL: {url}")
            print(f"   화질: {self.quality}")
            if self.audio_only:
                print(f"   모드: 오디오 전용 (MP3)")
            print(f"   저장 위치: {output_path}")
            print()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info first
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)

                print(f"📺 제목: {title}")
                print(f"⏱️  길이: {duration // 60}분 {duration % 60}초")
                print()

                # Download
                ydl.download([url])

            print(f"\n💾 저장 완료: {output_path}")
            return True

        except Exception as e:
            print(f"\n❌ 다운로드 실패: {e}")
            return False

    def get_video_info(self, url: str) -> dict:
        """
        Get video information without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary containing video information
        """
        ydl_opts = {"quiet": True, "no_warnings": True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date"),
            "description": info.get("description"),
            "formats": [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "filesize": f.get("filesize"),
                }
                for f in info.get("formats", [])
            ],
        }
