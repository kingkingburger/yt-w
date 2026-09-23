"""루트(/) 및 /health 엔드포인트."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


class RevalidatedStaticFiles(StaticFiles):
    """정적 자산마다 재검증을 강제한다.

    Cache-Control이 없으면 브라우저가 옛 CSS/JS를 추정 기간 동안 그대로 써서,
    새 index.html과 옛 app.css가 섞인 채 화면이 깨진다. no-cache는 ETag로
    매번 확인만 하므로 바뀌지 않은 파일은 304로 끝난다.
    """

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def register_meta_routes(app: FastAPI) -> None:
    web_dir = Path(__file__).resolve().parents[4] / "web"
    if web_dir.exists():
        app.mount("/static", RevalidatedStaticFiles(directory=web_dir), name="static")

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
