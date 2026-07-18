"""Video info, download, and file-response route contracts."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.channels.repository import ChannelManager


class TestVideoDownloadRoutes:
    def test_video_info_sanitizes_playlist_context_and_returns_contract(
        self, client: TestClient
    ):
        with patch(
            "src.yt_monitor.web.routes.video.VideoDownloader"
        ) as downloader_class:
            downloader_class.return_value.get_video_info.return_value = {
                "title": "Video",
                "uploader": "Channel",
                "duration": 123,
                "view_count": 456,
                "thumbnail": "https://example.com/thumb.jpg",
            }
            response = client.post(
                "/api/video/info",
                json={
                    "url": "https://www.youtube.com/watch?v=abc&list=PL1&index=2"
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "title": "Video",
            "uploader": "Channel",
            "duration": 123,
            "view_count": 456,
            "thumbnail": "https://example.com/thumb.jpg",
        }
        downloader_class.return_value.get_video_info.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc"
        )

    def test_video_info_timeout_returns_408(self, client: TestClient):
        with patch(
            "src.yt_monitor.web.routes.video.asyncio.to_thread",
            new=AsyncMock(side_effect=asyncio.TimeoutError),
        ):
            response = client.post(
                "/api/video/info",
                json={"url": "https://www.youtube.com/watch?v=abc"},
            )

        assert response.status_code == 408
        assert "timeout" in response.json()["detail"].lower()

    def test_video_info_failure_is_reported_without_crashing_server(
        self, client: TestClient
    ):
        with patch(
            "src.yt_monitor.web.routes.video.VideoDownloader"
        ) as downloader_class:
            downloader_class.return_value.get_video_info.side_effect = RuntimeError(
                "metadata unavailable"
            )
            response = client.post(
                "/api/video/info",
                json={"url": "https://www.youtube.com/watch?v=abc"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "metadata unavailable"

    @pytest.mark.parametrize(
        ("audio_only", "prefix", "extension"),
        [(False, "video", "mp4"), (True, "audio", "mp3")],
    )
    def test_download_uses_configured_directory_and_expected_filename(
        self,
        client: TestClient,
        channels_file: str,
        audio_only: bool,
        prefix: str,
        extension: str,
    ):
        manager = ChannelManager(channels_file)
        download_dir = (
            Path(manager.get_global_settings().download_directory) / "web_downloads"
        )
        with (
            patch(
                "src.yt_monitor.web.routes.video.VideoDownloader"
            ) as downloader_class,
            patch("src.yt_monitor.web.routes.video.datetime") as datetime_mock,
        ):
            downloader_class.return_value.download.return_value = True
            datetime_mock.now.return_value.strftime.return_value = "20260719_081500"
            response = client.post(
                "/api/download",
                json={
                    "url": "https://www.youtube.com/watch?v=abc&list=PL1",
                    "quality": "720",
                    "audio_only": audio_only,
                },
            )

        filename = f"{prefix}_20260719_081500.{extension}"
        assert response.status_code == 200
        assert response.json()["filename"] == filename
        assert response.json()["file_path"] == str(download_dir / filename)
        downloader_class.assert_called_once_with(
            output_dir=str(download_dir),
            quality="720",
            audio_only=audio_only,
        )
        downloader_class.return_value.download.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc",
            filename=f"{prefix}_20260719_081500",
        )

    def test_download_failure_returns_500(self, client: TestClient):
        with patch(
            "src.yt_monitor.web.routes.video.VideoDownloader"
        ) as downloader_class:
            downloader_class.return_value.download.return_value = False
            response = client.post(
                "/api/download",
                json={"url": "https://www.youtube.com/watch?v=abc"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Download failed"

    def test_download_file_returns_existing_content(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        web_downloads = (
            Path(manager.get_global_settings().download_directory) / "web_downloads"
        )
        web_downloads.mkdir(parents=True)
        (web_downloads / "ready.mp4").write_bytes(b"video-content")

        response = client.get("/api/download/file/ready.mp4")

        assert response.status_code == 200
        assert response.content == b"video-content"
        assert 'filename="ready.mp4"' in response.headers["content-disposition"]

    def test_download_file_rejects_path_escape(
        self, client: TestClient, channels_file: str
    ):
        from src.yt_monitor.channels.repository import ChannelManager

        manager = ChannelManager(channels_file)
        settings = manager.get_global_settings()
        download_root = Path(settings.download_directory)
        web_downloads = download_root / "web_downloads"
        web_downloads.mkdir(parents=True)
        (download_root / "secret.txt").write_text("secret", encoding="utf-8")

        response = client.get("/api/download/file/..%5Csecret.txt")

        assert response.status_code == 404
