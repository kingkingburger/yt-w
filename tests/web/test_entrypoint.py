"""Web runtime entry-point contracts."""

from unittest.mock import patch

import pytest

from src.yt_monitor.web import entrypoint


def test_main_starts_web_api_from_environment_port(monkeypatch) -> None:
    monkeypatch.setenv("YT_WEB_PORT", "9123")
    monkeypatch.delenv("YT_WEB_HOST", raising=False)

    with patch.object(entrypoint, "WebAPI") as web_api_class:
        entrypoint.main()

    web_api_class.assert_called_once_with(channels_file="channels.json")
    web_api_class.return_value.run.assert_called_once_with(
        host="127.0.0.1",
        port=9123,
    )


def test_main_allows_container_host_override(monkeypatch) -> None:
    monkeypatch.setenv("YT_WEB_PORT", "8011")
    monkeypatch.setenv("YT_WEB_HOST", "0.0.0.0")

    with patch.object(entrypoint, "WebAPI") as web_api_class:
        entrypoint.main()

    web_api_class.return_value.run.assert_called_once_with(
        host="0.0.0.0",
        port=8011,
    )


def test_main_rejects_invalid_environment_port(monkeypatch) -> None:
    monkeypatch.setenv("YT_WEB_PORT", "invalid")

    with pytest.raises(SystemExit, match="Invalid YT_WEB_PORT"):
        entrypoint.main()
