"""Keep successful uploads independently of the bounded in-memory job list."""

import sqlite3
from pathlib import Path


class UploadHistory:
    def __init__(self, root: Path):
        self.root = root

    def _connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.root / ".youtube-upload-history.sqlite3")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS uploads ("
            "source TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, video_id TEXT)"
        )
        return connection

    def record(self, source: str, size: int, mtime_ns: int, video_id: str) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO uploads VALUES (?, ?, ?, ?)",
                    (source, size, mtime_ns, video_id),
                )
        finally:
            connection.close()

    def list_current(self) -> list[dict[str, str]]:
        if not (self.root / ".youtube-upload-history.sqlite3").exists():
            return []
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT source, size, mtime_ns, video_id FROM uploads"
            ).fetchall()
        finally:
            connection.close()
        records = []
        for source, size, mtime_ns, video_id in rows:
            path = self.root / source
            try:
                path.resolve().relative_to(self.root.resolve())
                stat = path.stat()
            except (OSError, ValueError):
                continue
            if stat.st_size == size and stat.st_mtime_ns == mtime_ns:
                records.append({"source": source, "video_id": video_id})
        return records
