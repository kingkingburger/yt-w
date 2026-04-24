"""백그라운드 파일 정리 스케줄러 — WebAPI와 분리된 독립 책임."""

import threading
import time
from typing import Callable, Optional

from ..channel_manager import ChannelManager
from ..file_cleaner import FileCleaner
from ..logger import Logger


class CleanupScheduler:
    """주기적으로 FileCleaner를 호출한다. 중단 가능한 별도 스레드."""

    def __init__(
        self,
        channel_manager: ChannelManager,
        retention_days: int = 7,
        interval_seconds: int = 24 * 60 * 60,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._channel_manager = channel_manager
        self._retention_days = retention_days
        self._interval_seconds = interval_seconds
        self._sleep = sleep_fn
        self._logger = Logger.get()
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._logger.info("파일 자동 정리 스케줄러 시작됨 (매일 실행)")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running

    def run_once(self) -> None:
        """한 번의 정리 사이클을 실행한다 (테스트/수동 호출용)."""
        settings = self._channel_manager.get_global_settings()
        cleaner = FileCleaner(
            download_directory=settings.download_directory,
            retention_days=self._retention_days,
        )

        summary = cleaner.get_cleanup_summary()
        if summary["files_to_delete"] > 0:
            self._logger.info(
                f"자동 정리: {summary['files_to_delete']}개 파일 "
                f"({summary['total_size_mb']:.2f} MB) 삭제 예정"
            )
            cleaner.cleanup(dry_run=False)

    def _loop(self) -> None:
        while self._running:
            try:
                self.run_once()
            except Exception as error:
                self._logger.error(f"자동 정리 오류: {error}")

            for _ in range(self._interval_seconds):
                if not self._running:
                    break
                self._sleep(1)
