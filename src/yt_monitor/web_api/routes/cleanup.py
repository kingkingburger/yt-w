"""/api/cleanup, /api/cleanup/status 엔드포인트."""

from fastapi import FastAPI, HTTPException

from ...channel_manager import ChannelManager
from ...file_cleaner import FileCleaner
from ...logger import Logger
from ..schemas import CleanupRequest


def register_cleanup_routes(
    app: FastAPI,
    channel_manager: ChannelManager,
) -> None:
    logger = Logger.get()

    @app.get("/api/cleanup/status")
    async def get_cleanup_status():
        settings = channel_manager.get_global_settings()
        cleaner = FileCleaner(
            download_directory=settings.download_directory,
            retention_days=7,
        )
        summary = cleaner.get_cleanup_summary()

        return {
            "files_to_delete": summary["files_to_delete"],
            "total_size_mb": round(summary["total_size_mb"], 2),
            "retention_days": summary["retention_days"],
            "live_files_preserved": summary["live_files_preserved"],
            "live_size_mb": round(summary["live_size_mb"], 2),
        }

    @app.post("/api/cleanup")
    async def run_cleanup(request: CleanupRequest):
        try:
            settings = channel_manager.get_global_settings()
            cleaner = FileCleaner(
                download_directory=settings.download_directory,
                retention_days=request.retention_days,
            )

            summary = cleaner.get_cleanup_summary()

            if request.dry_run:
                old_files = cleaner.find_old_files()
                return {
                    "dry_run": True,
                    "files_to_delete": summary["files_to_delete"],
                    "total_size_mb": round(summary["total_size_mb"], 2),
                    "files": [
                        {"path": str(f[0]), "age_days": round(f[1], 1)}
                        for f in old_files
                    ],
                }

            deleted = cleaner.cleanup(dry_run=False)
            return {
                "dry_run": False,
                "deleted_count": len(deleted),
                "deleted_files": [str(f) for f in deleted],
            }

        except Exception as error:
            logger.error(f"Cleanup error: {error}")
            raise HTTPException(status_code=500, detail=str(error))
