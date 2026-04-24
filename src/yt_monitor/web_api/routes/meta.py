"""루트(/) 및 /health 엔드포인트."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def register_meta_routes(app: FastAPI) -> None:
    @app.get("/health")
    async def health_check():
        """Docker healthcheck용 엔드포인트."""
        return {"status": "ok"}

    @app.get("/")
    async def root():
        """웹 인터페이스 HTML 서빙."""
        html_file = Path(__file__).parent.parent.parent.parent.parent / "web" / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return {"message": "YouTube Live Monitor API"}
