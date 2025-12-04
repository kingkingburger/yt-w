"""General YouTube video downloader module."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp

from .cookie_helper import get_cookie_options


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

        # For video downloads, prefer m4a audio (AAC) over opus for Windows compatibility
        if self.quality == "best":
            return "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

        # Specific quality (e.g., 720, 1080)
        height = self.quality
        return f"bestvideo[height<={height}]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]"

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
            **get_cookie_options(),
            # Performance optimizations
            "concurrent_fragment_downloads": 8,  # Download 8 fragments in parallel
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            "buffersize": 1024 * 1024,  # 1MB buffer
            "http_chunk_size": 10485760,  # 10MB chunks
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
            # Merge video+audio to MP4 - CRITICAL for audio!
            opts["merge_output_format"] = "mp4"
            opts["prefer_ffmpeg"] = True
            opts["keepvideo"] = False  # Delete original files after merge

            # Use FFmpegVideoConvertor to ensure audio is AAC (Windows compatible)
            # This will convert Opus to AAC if needed
            opts["postprocessors"] = [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ]

            # Force audio conversion to AAC for Windows Media Player compatibility
            opts["postprocessor_args"] = {
                "FFmpegVideoConvertor": [
                    "-c:v",
                    "copy",  # Copy video (no re-encoding)
                    "-c:a",
                    "aac",  # Convert audio to AAC
                    "-b:a",
                    "192k",  # Audio bitrate
                    "-ar",
                    "48000",  # Sample rate
                ]
            }

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
            print("\n📥 다운로드 시작...")
            print(f"   URL: {url}")
            print(f"   화질: {self.quality}")
            if self.audio_only:
                print("   모드: 오디오 전용 (MP3)")
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
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "no_check_certificates": True,
            "socket_timeout": 30,
            **get_cookie_options(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date"),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
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
