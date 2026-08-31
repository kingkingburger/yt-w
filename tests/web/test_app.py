"""Tests for web_api module — /health 엔드포인트 검증."""

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from src.yt_monitor.web.app import WebAPI

CSS_ASSETS = ("app.css", "palette.css")
JS_ASSETS = (
    "palette_boot.js",
    "app_core.js",
    "merge_output_name.js",
    "merge_download_directory.js",
    "channels.js",
    "merge_files.js",
    "merge_sequence.js",
    "merge_jobs.js",
    "split.js",
    "youtube_upload.js",
    "download.js",
    "palette.js",
    "app.js",
)


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
        for filename in CSS_ASSETS:
            assert f'href="/static/{filename}"' in response.text
        for filename in JS_ASSETS:
            assert f'src="/static/{filename}"' in response.text

        ordered_runtime_assets = JS_ASSETS[1:]
        positions = [
            response.text.index(f'src="/static/{filename}"')
            for filename in ordered_runtime_assets
        ]
        assert positions == sorted(positions)

    def test_static_assets_are_served(self, client: TestClient):
        for filename in CSS_ASSETS:
            response = client.get(f"/static/{filename}")
            assert response.status_code == 200
            assert "text/css" in response.headers["content-type"]
        for filename in JS_ASSETS:
            response = client.get(f"/static/{filename}")
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"]
