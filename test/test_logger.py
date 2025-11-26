"""Tests for logger module."""

import logging
from pathlib import Path

import pytest

from src.yt_monitor.logger import Logger


class TestLogger:
    """Test cases for Logger class."""

    def setup_method(self):
        """Reset logger state before each test."""
        Logger._initialized = False
        Logger._instance = None

    def teardown_method(self):
        """Clean up logger state after each test."""
        # Close all handlers to release file locks on Windows
        if Logger._instance:
            for handler in Logger._instance.handlers[:]:
                handler.close()
                Logger._instance.removeHandler(handler)
        Logger._initialized = False
        Logger._instance = None

    def test_initialize_creates_logger(self, temp_log_file: Path):
        """Test that initialize creates a logger instance."""
        logger = Logger.initialize(str(temp_log_file))

        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert Logger._initialized is True

    def test_initialize_creates_log_file(self, temp_log_file: Path):
        """Test that initialize creates the log file."""
        Logger.initialize(str(temp_log_file))

        assert temp_log_file.exists()

    def test_initialize_creates_parent_directories(self, temp_dir: Path):
        """Test that initialize creates parent directories if needed."""
        nested_log_file = temp_dir / "nested" / "dir" / "test.log"
        Logger.initialize(str(nested_log_file))

        assert nested_log_file.parent.exists()

    def test_initialize_returns_same_instance_on_second_call(
        self, temp_log_file: Path
    ):
        """Test that initialize returns the same instance when called twice."""
        logger1 = Logger.initialize(str(temp_log_file))
        logger2 = Logger.initialize(str(temp_log_file))

        assert logger1 is logger2

    def test_get_returns_initialized_logger(self, temp_log_file: Path):
        """Test that get returns the initialized logger."""
        Logger.initialize(str(temp_log_file))
        logger = Logger.get()

        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_raises_error_when_not_initialized(self):
        """Test that get raises RuntimeError when logger not initialized."""
        with pytest.raises(RuntimeError, match="Logger not initialized"):
            Logger.get()

    def test_logger_writes_to_file(self, temp_log_file: Path):
        """Test that logger writes messages to the log file."""
        logger = Logger.initialize(str(temp_log_file))
        test_message = "Test log message"

        logger.info(test_message)

        log_content = temp_log_file.read_text()
        assert test_message in log_content

    def test_logger_has_correct_format(self, temp_log_file: Path):
        """Test that log messages have the expected format."""
        logger = Logger.initialize(str(temp_log_file))
        logger.info("Format test")

        log_content = temp_log_file.read_text()
        # Format: "YYYY-MM-DD HH:MM:SS - LEVEL - message"
        assert " - INFO - " in log_content

    def test_logger_default_level_is_info(self, temp_log_file: Path):
        """Test that the default log level is INFO."""
        logger = Logger.initialize(str(temp_log_file))

        assert logger.level == logging.INFO
