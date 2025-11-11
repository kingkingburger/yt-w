"""Tests for logger module."""

import pytest

from src.yt_monitor.logger import Logger


class TestLogger:
    """Test Logger singleton class."""

    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset logger state before each test."""
        yield
        if Logger._instance:
            for handler in Logger._instance.handlers[:]:
                handler.close()
                Logger._instance.removeHandler(handler)
        Logger._initialized = False
        Logger._instance = None

    def test_initialize_creates_logger(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger.initialize(log_file)

        assert logger is not None
        assert Logger._initialized is True
        assert Logger._instance is logger

    def test_initialize_creates_log_directory(self, tmp_path):
        log_file = str(tmp_path / "nested" / "test.log")
        Logger.initialize(log_file)

        assert (tmp_path / "nested").exists()

    def test_initialize_only_once(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger1 = Logger.initialize(log_file)
        logger2 = Logger.initialize(log_file)

        assert logger1 is logger2

    def test_get_returns_logger(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger.initialize(log_file)
        retrieved = Logger.get()

        assert retrieved is logger

    def test_get_without_initialize_raises_error(self):
        with pytest.raises(RuntimeError, match="Logger not initialized"):
            Logger.get()

    def test_logger_has_handlers(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger.initialize(log_file)

        assert len(logger.handlers) == 2
