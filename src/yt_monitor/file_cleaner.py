"""File cleanup module for managing downloaded files."""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from .logger import Logger


class FileCleaner:
    """Clean up old downloaded files based on retention policy."""

    def __init__(
        self,
        download_directory: str = "./downloads",
        retention_days: int = 7,
    ):
        """
        Initialize FileCleaner.

        Args:
            download_directory: Base directory for downloads
            retention_days: Number of days to keep files (default: 7)
        """
        self.download_directory = Path(download_directory)
        self.retention_days = retention_days
        self.logger = Logger.get()
        self.live_directory_name = "live"

    def _is_in_live_directory(self, file_path: Path) -> bool:
        """
        Check if file is inside the live directory.

        Args:
            file_path: Path to check

        Returns:
            True if file is in live directory, False otherwise
        """
        try:
            relative_path = file_path.relative_to(self.download_directory)
            parts = relative_path.parts
            return len(parts) > 0 and parts[0] == self.live_directory_name
        except ValueError:
            return False

    def _get_file_age_days(self, file_path: Path) -> float:
        """
        Get file age in days.

        Args:
            file_path: Path to file

        Returns:
            Age of file in days
        """
        modification_time = file_path.stat().st_mtime
        current_time = time.time()
        age_seconds = current_time - modification_time
        return age_seconds / (24 * 60 * 60)

    def find_old_files(self) -> List[Tuple[Path, float]]:
        """
        Find files older than retention period (excluding live directory).

        Returns:
            List of tuples containing (file_path, age_in_days)
        """
        old_files: List[Tuple[Path, float]] = []

        if not self.download_directory.exists():
            return old_files

        for file_path in self.download_directory.rglob("*"):
            if not file_path.is_file():
                continue

            if self._is_in_live_directory(file_path):
                continue

            age_days = self._get_file_age_days(file_path)
            if age_days >= self.retention_days:
                old_files.append((file_path, age_days))

        return sorted(old_files, key=lambda x: x[1], reverse=True)

    def cleanup(self, dry_run: bool = False) -> List[Path]:
        """
        Remove files older than retention period.

        Args:
            dry_run: If True, only report files without deleting

        Returns:
            List of deleted (or would be deleted) file paths
        """
        old_files = self.find_old_files()
        deleted_files: List[Path] = []

        if not old_files:
            self.logger.info("정리할 파일이 없습니다.")
            return deleted_files

        self.logger.info(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"{len(old_files)}개의 오래된 파일 발견 "
            f"({self.retention_days}일 이상 경과)"
        )

        for file_path, age_days in old_files:
            try:
                if dry_run:
                    self.logger.info(
                        f"[DRY RUN] 삭제 예정: {file_path} "
                        f"({age_days:.1f}일 경과)"
                    )
                else:
                    file_path.unlink()
                    self.logger.info(
                        f"삭제됨: {file_path} ({age_days:.1f}일 경과)"
                    )
                deleted_files.append(file_path)
            except OSError as error:
                self.logger.error(f"파일 삭제 실패: {file_path} - {error}")

        if not dry_run:
            self._remove_empty_directories()

        return deleted_files

    def _remove_empty_directories(self) -> None:
        """Remove empty directories after cleanup (excluding live directory)."""
        if not self.download_directory.exists():
            return

        for dir_path in sorted(
            self.download_directory.rglob("*"),
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            if not dir_path.is_dir():
                continue

            if self._is_in_live_directory(dir_path):
                continue

            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    self.logger.info(f"빈 디렉토리 삭제: {dir_path}")
            except OSError:
                pass

    def get_cleanup_summary(self) -> dict:
        """
        Get summary of files that would be cleaned up.

        Returns:
            Dictionary containing cleanup summary
        """
        old_files = self.find_old_files()
        total_size = sum(f[0].stat().st_size for f in old_files)

        live_dir = self.download_directory / self.live_directory_name
        live_file_count = 0
        live_total_size = 0

        if live_dir.exists():
            for file_path in live_dir.rglob("*"):
                if file_path.is_file():
                    live_file_count += 1
                    live_total_size += file_path.stat().st_size

        return {
            "files_to_delete": len(old_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "retention_days": self.retention_days,
            "live_files_preserved": live_file_count,
            "live_size_mb": live_total_size / (1024 * 1024),
        }
