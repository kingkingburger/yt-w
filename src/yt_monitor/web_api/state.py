"""실행 중인 모니터 상태 컨테이너 — 라우트 간 공유."""

import threading
from dataclasses import dataclass, field
from typing import Optional

from ..multi_channel_monitor import MultiChannelMonitor


@dataclass
class MonitorState:
    """현재 실행 중인 모니터와 그 스레드를 보관한다.

    라우트 함수들이 같은 인스턴스를 참조해 상태를 공유한다.
    """

    monitor: Optional[MultiChannelMonitor] = field(default=None)
    monitor_thread: Optional[threading.Thread] = field(default=None)

    @property
    def is_running(self) -> bool:
        return self.monitor is not None and self.monitor.is_running
