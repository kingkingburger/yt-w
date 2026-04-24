"""CleanupScheduler 단위 테스트 — 백그라운드 스레드 생명주기와 run_once 동작."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.channel_manager import GlobalSettingsDTO
from src.yt_monitor.web_api.cleanup_scheduler import CleanupScheduler


@pytest.fixture
def mock_channel_manager(tmp_path: Path) -> MagicMock:
    manager = MagicMock()
    manager.get_global_settings.return_value = GlobalSettingsDTO(
        download_directory=str(tmp_path / "downloads"),
        log_file=str(tmp_path / "test.log"),
    )
    return manager


class TestCleanupSchedulerRunOnce:
    """run_once는 FileCleaner를 한 번 실행한다."""

    def test_run_once_invokes_file_cleaner(
        self, mock_channel_manager: MagicMock, initialized_logger
    ):
        mock_cleaner_cls = MagicMock()
        mock_cleaner_instance = MagicMock()
        mock_cleaner_instance.get_cleanup_summary.return_value = {
            "files_to_delete": 3,
            "total_size_mb": 5.0,
        }
        mock_cleaner_cls.return_value = mock_cleaner_instance

        scheduler = CleanupScheduler(channel_manager=mock_channel_manager)

        with patch(
            "src.yt_monitor.web_api.cleanup_scheduler.FileCleaner", mock_cleaner_cls
        ):
            scheduler.run_once()

        mock_cleaner_cls.assert_called_once()
        mock_cleaner_instance.cleanup.assert_called_once_with(dry_run=False)

    def test_run_once_skips_cleanup_when_no_files(
        self, mock_channel_manager: MagicMock, initialized_logger
    ):
        mock_cleaner_cls = MagicMock()
        mock_cleaner_instance = MagicMock()
        mock_cleaner_instance.get_cleanup_summary.return_value = {
            "files_to_delete": 0,
            "total_size_mb": 0.0,
        }
        mock_cleaner_cls.return_value = mock_cleaner_instance

        scheduler = CleanupScheduler(channel_manager=mock_channel_manager)

        with patch(
            "src.yt_monitor.web_api.cleanup_scheduler.FileCleaner", mock_cleaner_cls
        ):
            scheduler.run_once()

        mock_cleaner_instance.cleanup.assert_not_called()


class TestCleanupSchedulerLifecycle:
    """start()/stop() — 스레드 생명주기."""

    def test_start_marks_running(
        self, mock_channel_manager: MagicMock, initialized_logger
    ):
        scheduler = CleanupScheduler(
            channel_manager=mock_channel_manager,
            sleep_fn=lambda _s: None,
        )

        with patch.object(scheduler, "run_once"):
            scheduler.start()
            try:
                assert scheduler.is_running is True
            finally:
                scheduler.stop()

        assert scheduler.is_running is False

    def test_start_is_idempotent(
        self, mock_channel_manager: MagicMock, initialized_logger
    ):
        """start()를 두 번 호출해도 스레드는 하나만."""
        scheduler = CleanupScheduler(
            channel_manager=mock_channel_manager,
            sleep_fn=lambda _s: None,
        )

        with patch.object(scheduler, "run_once"):
            scheduler.start()
            first_thread = scheduler._thread
            scheduler.start()
            assert scheduler._thread is first_thread
            scheduler.stop()

    def test_stop_without_start_is_safe(
        self, mock_channel_manager: MagicMock, initialized_logger
    ):
        """start 안 했는데 stop 호출해도 에러 없음."""
        scheduler = CleanupScheduler(channel_manager=mock_channel_manager)
        scheduler.stop()
        assert scheduler.is_running is False
