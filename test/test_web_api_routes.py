"""분리된 web_api 라우트들의 기본 동작 확인 통합 테스트."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.cookie_validator import invalidate_cookie_cache
from src.yt_monitor.web_api import WebAPI


@pytest.fixture(autouse=True)
def reset_cookie_cache():
    invalidate_cookie_cache()
    yield
    invalidate_cookie_cache()


@pytest.fixture
def channels_file(tmp_path: Path) -> str:
    data = {
        "channels": [],
        "global_settings": {
            "check_interval_seconds": 60,
            "download_directory": str(tmp_path / "downloads"),
            "log_file": str(tmp_path / "test.log"),
            "split_mode": "time",
            "split_time_minutes": 30,
            "split_size_mb": 500,
        },
    }
    path = tmp_path / "channels.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def client(channels_file: str) -> TestClient:
    web_api = WebAPI(channels_file=channels_file)
    return TestClient(web_api.app)


class TestChannelRoutes:
    """CRUD /api/channels."""

    def test_list_empty(self, client: TestClient):
        response = client.get("/api/channels")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_and_list(self, client: TestClient):
        payload = {
            "name": "TestCh",
            "url": "https://www.youtube.com/@TestCh",
        }
        created = client.post("/api/channels", json=payload).json()
        assert created["name"] == "TestCh"
        assert "id" in created

        listed = client.get("/api/channels").json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client: TestClient):
        response = client.get("/api/channels/not-a-real-id")
        assert response.status_code == 404

    def test_update_channel(self, client: TestClient):
        created = client.post(
            "/api/channels",
            json={"name": "Old", "url": "https://www.youtube.com/@Old"},
        ).json()

        updated = client.patch(
            f"/api/channels/{created['id']}", json={"name": "New"}
        ).json()

        assert updated["name"] == "New"

    def test_delete_channel(self, client: TestClient):
        created = client.post(
            "/api/channels",
            json={"name": "Temp", "url": "https://www.youtube.com/@Temp"},
        ).json()

        response = client.delete(f"/api/channels/{created['id']}")
        assert response.status_code == 200

        listed = client.get("/api/channels").json()
        assert listed == []

    def test_create_duplicate_url_returns_400(self, client: TestClient):
        payload = {"name": "A", "url": "https://www.youtube.com/@DupCh"}
        client.post("/api/channels", json=payload)
        response = client.post("/api/channels", json=payload)
        assert response.status_code == 400


class TestSettingsRoutes:
    """/api/settings."""

    def test_get_settings_returns_defaults(self, client: TestClient):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["check_interval_seconds"] == 60
        assert data["split_mode"] == "time"

    def test_patch_settings_updates_field(self, client: TestClient):
        response = client.patch(
            "/api/settings", json={"check_interval_seconds": 120}
        )
        assert response.status_code == 200
        assert response.json()["check_interval_seconds"] == 120


class TestMonitorStatusRoute:
    """/api/monitor/status."""

    def test_status_when_no_channels(self, client: TestClient):
        response = client.get("/api/monitor/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["active_channels"] == 0
        assert data["total_channels"] == 0

    def test_status_counts_channels(self, client: TestClient):
        client.post(
            "/api/channels",
            json={"name": "A", "url": "https://www.youtube.com/@A"},
        )
        client.post(
            "/api/channels",
            json={
                "name": "B",
                "url": "https://www.youtube.com/@B",
                "enabled": False,
            },
        )

        data = client.get("/api/monitor/status").json()
        assert data["total_channels"] == 2
        assert data["active_channels"] == 1


class TestCleanupStatusRoute:
    """/api/cleanup/status."""

    def test_empty_directory_zero_files(self, client: TestClient):
        response = client.get("/api/cleanup/status")
        assert response.status_code == 200
        data = response.json()
        assert data["files_to_delete"] == 0
        assert data["retention_days"] == 7
