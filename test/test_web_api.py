"""Tests for web_api module — /health 엔드포인트 검증."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.web_api import WebAPI


@pytest.fixture
def channels_file(tmp_path: Path) -> str:
    """임시 channels.json 파일 경로를 반환한다."""
    channels_data = {
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
    channels_path = tmp_path / "channels.json"
    channels_path.write_text(json.dumps(channels_data), encoding="utf-8")
    return str(channels_path)


@pytest.fixture
def client(channels_file: str) -> TestClient:
    """FastAPI TestClient를 반환한다."""
    web_api = WebAPI(channels_file=channels_file)
    return TestClient(web_api.app)


class TestHealthEndpoint:
    """GET /health 엔드포인트 검증."""

    def test_health_returns_200(self, client: TestClient):
        """GET /health는 HTTP 200을 반환한다."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client: TestClient):
        """GET /health 응답 본문에 status: ok가 포함된다."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_health_content_type_is_json(self, client: TestClient):
        """GET /health 응답은 JSON Content-Type이다."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_is_reachable_without_auth(self, client: TestClient):
        """GET /health는 인증 없이 접근 가능하다 (Docker probe용)."""
        # /health는 별도 설정 없이 항상 응답해야 한다
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code == 200
