"""Logging configuration module."""

import logging
from pathlib import Path
from typing import Optional


class Logger:
    _instance: Optional[logging.Logger] = None
    _initialized: bool = False

    @classmethod
    def initialize(cls, log_file: str, level: int = logging.INFO) -> logging.Logger:
        if cls._initialized:
            return cls._instance

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger('yt_monitor')
        logger.setLevel(level)
        logger.handlers.clear()

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        cls._instance = logger
        cls._initialized = True

        return logger

    @classmethod
    def get(cls) -> logging.Logger:
        if not cls._initialized or cls._instance is None:
            raise RuntimeError("Logger not initialized. Call Logger.initialize() first.")
        return cls._instance
