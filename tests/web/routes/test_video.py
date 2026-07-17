"""Video download route contracts."""

from pathlib import Path

from fastapi.testclient import TestClient


class TestVideoDownloadRoutes:
    """/api/download/file path safety."""

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
