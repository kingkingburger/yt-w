"""루트(/) 및 /health 엔드포인트."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


def register_meta_routes(app: FastAPI) -> None:
    web_dir = Path(__file__).resolve().parents[4] / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/health")
    async def health_check():
        """Docker healthcheck용 엔드포인트."""
        return {"status": "ok"}

    @app.get("/")
    async def root():
        """웹 인터페이스 HTML 서빙."""
        html_file = web_dir / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return {"message": "YouTube Live Monitor API"}
