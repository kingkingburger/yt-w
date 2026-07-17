"""Tests for web_api module — /health 엔드포인트 검증."""

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from src.yt_monitor.web.app import WebAPI


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
