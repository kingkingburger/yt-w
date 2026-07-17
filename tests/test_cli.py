"""CLI entrypoint regression tests."""

from types import SimpleNamespace
from unittest.mock import patch

import src.yt_monitor.cli as monitoring
from src.yt_monitor.channels.models import GlobalSettingsDTO


def test_download_mode_uses_global_default_directory_when_output_omitted():
    args = SimpleNamespace(
        output=None,
        quality="best",
        audio_only=False,
        url="https://www.youtube.com/watch?v=test",
        filename=None,
    )

    with patch.object(monitoring, "VideoDownloader") as downloader_cls:
        downloader_cls.return_value.download.return_value = True

        monitoring.download_mode(args)

    downloader_cls.assert_called_once_with(
        output_dir=GlobalSettingsDTO().download_directory,
        quality="best",
        audio_only=False,
    )
