"""Logging configuration module."""

import logging
import os
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class Logger:
    _instance: Optional[logging.Logger] = None
    _initialized: bool = False
    _log_directory: Optional[Path] = None
    _retention_days: int = 7

    @classmethod
    def initialize(
        cls,
        log_file: str,
        level: int = logging.INFO,
        retention_days: int = 7,
    ) -> logging.Logger:
        if cls._initialized:
            return cls._instance

        log_path = Path(log_file)
        cls._log_directory = log_path.parent
        cls._log_directory.mkdir(parents=True, exist_ok=True)
        cls._retention_days = retention_days

        logger = logging.getLogger("yt_monitor")
        logger.setLevel(level)
        logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=retention_days,
            encoding="utf-8",
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        cls._instance = logger
        cls._initialized = True

        cls._cleanup_old_logs()

        return logger

    @classmethod
    def _cleanup_old_logs(cls) -> None:
        """Remove log files older than retention_days."""
        if cls._log_directory is None:
            return

        cutoff_date = datetime.now() - timedelta(days=cls._retention_days)

        for log_file in cls._log_directory.glob("*.log*"):
            try:
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    os.remove(log_file)
            except OSError:
                pass

    @classmethod
    def get(cls) -> logging.Logger:
        if not cls._initialized or cls._instance is None:
            raise RuntimeError(
                "Logger not initialized. Call Logger.initialize() first."
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset logger state for testing purposes."""
        if cls._instance is not None:
            for handler in cls._instance.handlers[:]:
                handler.close()
                cls._instance.removeHandler(handler)
        cls._instance = None
        cls._initialized = False
        cls._log_directory = None
