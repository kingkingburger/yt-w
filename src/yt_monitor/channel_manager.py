"""Channel management module for multiple YouTube channels."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4


@dataclass
class ChannelDTO:
    """Data transfer object for YouTube channel information."""

    id: str
    name: str
    url: str
    enabled: bool = True
    download_format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]"

    def __post_init__(self):
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
    log_file: str = "./live_monitor.log"
    split_mode: str = "time"
    split_time_minutes: int = 30
    split_size_mb: int = 500

    def __post_init__(self):
        """Validate settings after initialization."""
        if self.check_interval_seconds < 1:
            raise ValueError("check_interval_seconds must be at least 1")
        if self.split_mode not in ["time", "size", "none"]:
            raise ValueError("split_mode must be 'time', 'size', or 'none'")


class ChannelManager:
    """Manage multiple YouTube channels for live stream monitoring."""

    def __init__(self, channels_file: str = "channels.json"):
        """
        Initialize ChannelManager.

        Args:
            channels_file: Path to channels configuration file
        """
        self.channels_file = Path(channels_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create channels file with default structure if it doesn't exist."""
        if not self.channels_file.exists():
            default_data = {
                "channels": [],
                "global_settings": asdict(GlobalSettingsDTO()),
            }
            self._write_data(default_data)

    def _read_data(self) -> Dict[str, Any]:
        """
        Read channels data from file.

        Returns:
            Dictionary containing channels and settings
        """
        with open(self.channels_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_data(self, data: Dict[str, Any]) -> None:
        """
        Write channels data to file.

        Args:
            data: Dictionary containing channels and settings
        """
        with open(self.channels_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_channel(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        download_format: str = "bestvideo[height<=720]+bestaudio/best[height<=720]",
    ) -> ChannelDTO:
        """
        Add a new channel to monitoring list.

        Args:
            name: Channel display name
            url: YouTube channel URL
            enabled: Whether to monitor this channel
            download_format: yt-dlp format string

        Returns:
            Created ChannelDTO object

        Raises:
            ValueError: If channel with same URL already exists
        """
        data = self._read_data()

        # Check if channel URL already exists
        for channel_data in data["channels"]:
            if channel_data["url"] == url:
                raise ValueError(f"Channel with URL {url} already exists")

        # Create new channel with unique ID
        channel = ChannelDTO(
            id=str(uuid4()),
            name=name,
            url=url,
            enabled=enabled,
            download_format=download_format,
        )

        data["channels"].append(asdict(channel))
        self._write_data(data)

        return channel

    def remove_channel(self, channel_id: str) -> bool:
        """
        Remove a channel by ID.

        Args:
            channel_id: Unique channel identifier

        Returns:
            True if channel was removed, False if not found
        """
        data = self._read_data()
        original_count = len(data["channels"])

        data["channels"] = [
            ch for ch in data["channels"] if ch["id"] != channel_id
        ]

        if len(data["channels"]) < original_count:
            self._write_data(data)
            return True

        return False

    def list_channels(self, enabled_only: bool = False) -> List[ChannelDTO]:
        """
        Get list of all channels.

        Args:
            enabled_only: If True, return only enabled channels

        Returns:
            List of ChannelDTO objects
        """
        data = self._read_data()
        channels = [ChannelDTO(**ch) for ch in data["channels"]]

        if enabled_only:
            channels = [ch for ch in channels if ch.enabled]

        return channels

    def get_channel(self, channel_id: str) -> Optional[ChannelDTO]:
        """
        Get a specific channel by ID.

        Args:
            channel_id: Unique channel identifier

        Returns:
            ChannelDTO if found, None otherwise
        """
        data = self._read_data()

        for channel_data in data["channels"]:
            if channel_data["id"] == channel_id:
                return ChannelDTO(**channel_data)

        return None

    def update_channel(
        self,
        channel_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        enabled: Optional[bool] = None,
        download_format: Optional[str] = None,
    ) -> Optional[ChannelDTO]:
        """
        Update channel information.

        Args:
            channel_id: Unique channel identifier
            name: New channel name (optional)
            url: New channel URL (optional)
            enabled: New enabled status (optional)
            download_format: New download format (optional)

        Returns:
            Updated ChannelDTO if found, None otherwise
        """
        data = self._read_data()

        for i, channel_data in enumerate(data["channels"]):
            if channel_data["id"] == channel_id:
                if name is not None:
                    channel_data["name"] = name
                if url is not None:
                    channel_data["url"] = url
                if enabled is not None:
                    channel_data["enabled"] = enabled
                if download_format is not None:
                    channel_data["download_format"] = download_format

                data["channels"][i] = channel_data
                self._write_data(data)

                return ChannelDTO(**channel_data)

        return None

    def get_global_settings(self) -> GlobalSettingsDTO:
        """
        Get global settings.

        Returns:
            GlobalSettingsDTO object
        """
        data = self._read_data()
        return GlobalSettingsDTO(**data["global_settings"])

    def update_global_settings(self, **kwargs) -> GlobalSettingsDTO:
        """
        Update global settings.

        Args:
            **kwargs: Settings to update

        Returns:
            Updated GlobalSettingsDTO object
        """
        data = self._read_data()
        settings = data["global_settings"]

        for key, value in kwargs.items():
            if key in settings:
                settings[key] = value

        data["global_settings"] = settings
        self._write_data(data)

        return GlobalSettingsDTO(**settings)
