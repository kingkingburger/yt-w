"""Monitor runtime entry-point contracts."""

from types import SimpleNamespace
from unittest.mock import patch

from src.yt_monitor import entrypoint


def test_main_starts_monitor_for_enabled_channels() -> None:
    settings = SimpleNamespace(log_file="logs/test.log")

    with (
        patch.object(entrypoint, "ChannelManager") as manager_class,
        patch.object(entrypoint, "Logger") as logger,
        patch.object(entrypoint, "MultiChannelMonitor") as monitor_class,
    ):
        manager = manager_class.return_value
        manager.list_channels.return_value = [object()]
        manager.get_global_settings.return_value = settings

        entrypoint.main()

    manager_class.assert_called_once_with(channels_file="channels.json")
    manager.list_channels.assert_called_once_with(enabled_only=True)
    logger.initialize.assert_called_once_with(log_file=settings.log_file)
    monitor_class.assert_called_once_with(channel_manager=manager)
    monitor_class.return_value.start.assert_called_once_with()


def test_main_without_enabled_channels_exits_without_starting_monitor() -> None:
    with (
        patch.object(entrypoint, "ChannelManager") as manager_class,
        patch.object(entrypoint, "MultiChannelMonitor") as monitor_class,
    ):
        manager_class.return_value.list_channels.return_value = []

        entrypoint.main()

    monitor_class.assert_not_called()
