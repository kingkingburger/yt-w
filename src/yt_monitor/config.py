"""Configuration management module."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any


@dataclass
class Config:
    """Configuration data class."""

    channel_url: str
    check_interval_seconds: int
    download_directory: str
    log_file: str
    video_quality: str
    download_format: str

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if not self.channel_url:
            raise ValueError("channel_url cannot be empty")

        if self.check_interval_seconds < 1:
            raise ValueError("check_interval_seconds must be at least 1")

        if not self.download_directory:
            raise ValueError("download_directory cannot be empty")

        if not self.log_file:
            raise ValueError("log_file cannot be empty")


class ConfigLoader:
    """Load and validate configuration from JSON file."""

    DEFAULT_CONFIG = {
        'channel_url': '',
        'check_interval_seconds': 60,
        'download_directory': './downloads',
        'log_file': './live_monitor.log',
        'video_quality': 'best',
        'download_format': 'bestvideo+bestaudio/best'
    }

    @classmethod
    def load(cls, config_path: str = "config.json") -> Config:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config object with loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

        config_data = {**cls.DEFAULT_CONFIG, **data}
        return Config(**config_data)

    @classmethod
    def load_dict(cls, config_dict: Dict[str, Any]) -> Config:
        """
        Load configuration from dictionary.

        Args:
            config_dict: Dictionary containing configuration

        Returns:
            Config object with loaded configuration
        """
        config_data = {**cls.DEFAULT_CONFIG, **config_dict}
        return Config(**config_data)
