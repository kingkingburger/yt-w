"""작업 DTO의 종료 시각 기록."""

from __future__ import annotations

import time
from typing import Optional, Protocol


class FinishableJobProtocol(Protocol):
    """종료 시각과 경과 시간을 함께 갖는 작업 DTO."""

    started_at: float
    finished_at: Optional[float]
    elapsed_seconds: float


def stamp_job_finished(job: FinishableJobProtocol) -> None:
    """먼저 기록된 종료 시각은 그대로 두고 경과 시간을 확정한다."""
    if job.finished_at is None:
        job.finished_at = time.time()
    job.elapsed_seconds = job.finished_at - job.started_at
