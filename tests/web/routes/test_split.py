"""Video split route contracts."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.yt_monitor.channels.repository import ChannelManager
from src.yt_monitor.media.split import SplitJobDTO, SplitJobManager

class TestSplitRoutes:
    """영상 분할 작업 API."""

    def test_submit_split_job(self, client: TestClient, channels_file: str):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "long.mp4").write_bytes(b"video")

        with (
            patch(
                "src.yt_monitor.media.split.probe_duration_seconds",
                return_value=13 * 3600,
            ),
            patch.object(SplitJobManager, "_run"),
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

    def test_upload_rejects_empty_body_and_removes_temporary_file(
        self, client: TestClient, channels_file: str
    ):
        response = client.post(
            "/api/split/upload",
            params={"filename": "empty.mp4"},
            content=b"",
            headers={"Content-Type": "video/mp4"},
        )

        root = Path(ChannelManager(channels_file).get_global_settings().download_directory)
        assert response.status_code == 400
        assert "빈 파일" in response.json()["detail"]
        assert list((root / "uploads").glob(".upload-*.part")) == []
        assert not (root / "uploads" / "empty.mp4").exists()

    def test_submit_get_cancel_and_not_ready_download(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "video.mp4").write_bytes(b"video")
        with (
            patch(
                "src.yt_monitor.media.split.probe_duration_seconds",
                return_value=120,
            ),
            patch.object(SplitJobManager, "_run"),
        ):
            submitted = client.post(
                "/api/split",
                json={"input": "video.mp4", "strategy": "parts", "parts": 2},
            )

        job = submitted.json()
        assert submitted.status_code == 200
        assert client.get(f"/api/split/jobs/{job['id']}").json() == job
        assert [item["id"] for item in client.get("/api/split/jobs").json()] == [
            job["id"]
        ]
        assert client.post(f"/api/split/jobs/{job['id']}/cancel").json() == {
            "cancelled": True
        }
        assert client.post(f"/api/split/jobs/{job['id']}/cancel").status_code == 400
        assert (
            client.get(f"/api/split/jobs/{job['id']}/download/1").status_code == 404
        )

    def test_download_returns_completed_split_part(
        self, client: TestClient, tmp_path: Path
    ):
        output = tmp_path / "video-1.mp4"
        output.write_bytes(b"split-part")
        job = SplitJobDTO(
            id="split-1",
            input="video.mp4",
            outputs=["split/video-1.mp4"],
            strategy="parts",
            interval_seconds=None,
            parts=1,
            duration_seconds=60.0,
            total_parts=1,
            completed_parts=1,
            status="done",
            started_at=1.0,
            finished_at=2.0,
            message="완료",
            elapsed_seconds=1.0,
        )
        with (
            patch.object(SplitJobManager, "get", return_value=job),
            patch.object(SplitJobManager, "output_path", return_value=output),
        ):
            response = client.get("/api/split/jobs/split-1/download/1")

        assert response.status_code == 200
        assert response.content == b"split-part"
