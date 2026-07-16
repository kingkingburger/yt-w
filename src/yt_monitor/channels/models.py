"""Channel and global configuration data contracts."""

from dataclasses import dataclass


@dataclass
class ChannelDTO:
    """Data transfer object for YouTube channel information."""

    id: str
    name: str
    url: str
    enabled: bool = True
    download_format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]"

    def __post_init__(self) -> None:
        """Validate channel data after initialization."""
        if not self.url:
            raise ValueError("Channel URL cannot be empty")
        if not self.name:
            raise ValueError("Channel name cannot be empty")


@dataclass
class GlobalSettingsDTO:
    """Global settings for all channels."""

    check_interval_seconds: int = 60
    download_directory: str = "./downloads"
    log_file: str = "./logs/live_monitor.log"
    split_mode: str = "time"
    split_time_minutes: int = 30
    split_size_mb: int = 500

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if self.check_interval_seconds < 1:
            raise ValueError("check_interval_seconds must be at least 1")
        if self.split_mode not in ["time", "size", "none"]:
            raise ValueError("split_mode must be 'time', 'size', or 'none'")
