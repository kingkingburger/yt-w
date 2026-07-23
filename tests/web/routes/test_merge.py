"""Merge workspace API lifecycle contracts."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.yt_monitor.channels.repository import ChannelManager
from src.yt_monitor.media.merge import MergeJobDTO, MergeJobManager


class TestMergeRoutes:
    def test_file_list_cache_can_be_explicitly_refreshed(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "one.mp4").write_bytes(b"one")

        first = client.get("/api/files").json()
        (root / "two.mkv").write_bytes(b"two")
        cached = client.get("/api/files").json()
        refreshed = client.get("/api/files?refresh=true").json()

        assert [item["path"] for item in first] == ["one.mp4"]
        assert cached == first
        assert {item["path"] for item in refreshed} == {"one.mp4", "two.mkv"}

    def test_delete_files_removes_batch_and_invalidates_cache(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        (root / "parts").mkdir(parents=True)
        (root / "parts" / "one.mp4").write_bytes(b"one")
        (root / "parts" / "two.mkv").write_bytes(b"two")
        (root / "keep.mp4").write_bytes(b"keep")
        assert len(client.get("/api/files").json()) == 3

        response = client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["parts/one.mp4", "parts/two.mkv"]},
        )

        assert response.status_code == 200
        assert response.json() == {
            "deleted": ["parts/one.mp4", "parts/two.mkv"],
            "count": 2,
        }
        assert not (root / "parts" / "one.mp4").exists()
        assert not (root / "parts" / "two.mkv").exists()
        assert [item["path"] for item in client.get("/api/files").json()] == [
            "keep.mp4"
        ]

    def test_delete_files_rejects_outside_download_root(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        outside = root.parent / "outside.mp4"
        outside.write_bytes(b"outside")

        response = client.request(
            "DELETE", "/api/files", json={"paths": ["../outside.mp4"]}
        )

        assert response.status_code == 400
        assert outside.read_bytes() == b"outside"

    def test_delete_files_validates_entire_batch_before_unlinking(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        existing = root / "existing.mp4"
        existing.write_bytes(b"existing")

        response = client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["existing.mp4", "missing.mp4"]},
        )

        assert response.status_code == 404
        assert existing.read_bytes() == b"existing"

    def test_submit_list_get_cancel_and_not_ready_download(
        self, client: TestClient, channels_file: str
    ):
        manager = ChannelManager(channels_file)
        root = Path(manager.get_global_settings().download_directory)
        root.mkdir(parents=True)
        (root / "one.mp4").write_bytes(b"one")
        (root / "two.mp4").write_bytes(b"two")

        with patch.object(MergeJobManager, "_run"):
            submitted = client.post(
                "/api/merge",
                json={
                    "inputs": ["one.mp4", "two.mp4"],
                    "output": "joined",
                    "mode": "concat",
                },
            )

        assert submitted.status_code == 200
        job = submitted.json()
        assert job["status"] == "queued"
        assert job["output"] == "merged/joined.mp4"
        assert client.get(f"/api/merge/jobs/{job['id']}").json() == job
        assert [item["id"] for item in client.get("/api/merge/jobs").json()] == [
            job["id"]
        ]

        cancelled = client.post(f"/api/merge/jobs/{job['id']}/cancel")
        assert cancelled.json() == {"cancelled": True}
        assert client.post(f"/api/merge/jobs/{job['id']}/cancel").status_code == 400
        assert (
            client.get(f"/api/merge/jobs/{job['id']}/download").status_code == 404
        )

    def test_download_returns_completed_merge_output(self, client: TestClient, tmp_path: Path):
        output = tmp_path / "ready.mp4"
        output.write_bytes(b"merged-video")
        job = MergeJobDTO(
            id="job-1",
            inputs=["one.mp4", "two.mp4"],
            output="merged/ready.mp4",
            mode="concat",
            status="done",
            started_at=1.0,
            finished_at=2.0,
            message="병합 완료",
            elapsed_seconds=1.0,
        )

        with (
            patch.object(MergeJobManager, "get", return_value=job),
            patch.object(MergeJobManager, "output_path", return_value=output),
        ):
            response = client.get("/api/merge/jobs/job-1/download")

        assert response.status_code == 200
        assert response.content == b"merged-video"
        assert 'filename="ready.mp4"' in response.headers["content-disposition"]
