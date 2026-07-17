"""Video split route contracts."""

from pathlib import Path

from fastapi.testclient import TestClient

class TestSplitRoutes:
    """영상 분할 작업 API."""

    def test_submit_split_job(self, client: TestClient, channels_file: str):
        from unittest.mock import patch

        from src.yt_monitor.channels.repository import ChannelManager

        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "long.mp4").write_bytes(b"video")

        with (
            patch(
                "src.yt_monitor.media.split.probe_duration_seconds",
                return_value=13 * 3600,
            ),
            patch("src.yt_monitor.media.split.threading.Thread"),
        ):
            response = client.post(
                "/api/split",
                json={"input": "long.mp4", "strategy": "parts", "parts": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_parts"] == 3
        assert data["outputs"] == [
            "split/long-1.mp4",
            "split/long-2.mp4",
            "split/long-3.mp4",
        ]

    def test_split_rejects_missing_strategy_value(
        self, client: TestClient, channels_file: str
    ):
        from src.yt_monitor.channels.repository import ChannelManager

        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "long.mp4").write_bytes(b"video")

        response = client.post(
            "/api/split",
            json={"input": "long.mp4", "strategy": "interval"},
        )

        assert response.status_code == 400
        assert "간격" in response.json()["detail"]

    def test_upload_split_video_and_refresh_file_list(
        self, client: TestClient, channels_file: str
    ):
        assert client.get("/api/files").json() == []

        response = client.post(
            "/api/split/upload",
            params={"filename": "my-video.mp4"},
            content=b"video-bytes",
            headers={"Content-Type": "video/mp4"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "path": "uploads/my-video.mp4",
            "name": "my-video.mp4",
            "size_bytes": 11,
        }
        refreshed = client.get("/api/files?refresh=true").json()
        assert [item["path"] for item in refreshed] == ["uploads/my-video.mp4"]

    def test_upload_uses_numbered_name_when_file_exists(
        self, client: TestClient
    ):
        first = client.post(
            "/api/split/upload",
            params={"filename": "same.mkv"},
            content=b"first",
            headers={"Content-Type": "video/x-matroska"},
        )
        second = client.post(
            "/api/split/upload",
            params={"filename": "same.mkv"},
            content=b"second",
            headers={"Content-Type": "video/x-matroska"},
        )

        assert first.json()["path"] == "uploads/same.mkv"
        assert second.json()["path"] == "uploads/same-2.mkv"

    def test_upload_rejects_unsupported_extension(self, client: TestClient):
        response = client.post(
            "/api/split/upload",
            params={"filename": "notes.txt"},
            content=b"not-video",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 400
        assert "형식" in response.json()["detail"]
