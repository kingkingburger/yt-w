"""Tests for web_api module — /health 엔드포인트 검증."""

import json
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yt_monitor.web.app import WebAPI


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

    def test_app_version_matches_pyproject(self, channels_file: str):
        pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        web_api = WebAPI(channels_file=channels_file)

        assert web_api.app.version == pyproject["project"]["version"]

    def test_health_contract_for_docker_probe(self, client: TestClient):
        """Docker probe가 인증 없이 호출할 수 있는 JSON health 계약을 보존한다."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "application/json" in response.headers["content-type"]


class TestWebAssets:
    """루트 HTML과 분리된 정적 자산 서빙 검증."""

    def test_root_references_extracted_assets(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert 'href="/static/app.css"' in response.text
        assert 'src="/static/app.js"' in response.text

    def test_static_assets_are_served(self, client: TestClient):
        css = client.get("/static/app.css")
        js = client.get("/static/app.js")

        assert css.status_code == 200
        assert "text/css" in css.headers["content-type"]
        assert js.status_code == 200
        assert "javascript" in js.headers["content-type"]
