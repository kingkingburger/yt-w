"""AlertCooldown 값 객체 — 쿨다운 창 내 최대 1회 통과."""

import time
from typing import Callable, Optional


class AlertCooldown:
    """쿨다운 창 안에서는 첫 호출만 True, 나머지는 False를 반환한다.

    알림 폭주 방지용. `clock`을 주입하면 테스트에서 시간 조작이 쉽다.
    """

    def __init__(
        self,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.time,
    ):
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self._cooldown_seconds: float = cooldown_seconds
        self._clock: Callable[[], float] = clock
        # None sentinel — 0.0을 쓰면 falsy 단락 때문에 clock이 0.0을 반환하는
        # 경우 첫 호출이 항상 통과로 처리되는 모호한 분기가 생긴다.
        self._last_at: Optional[float] = None

    def try_acquire(self) -> bool:
        """쿨다운 창 안이면 False, 통과 가능하면 True(= 방금 발생 기록)."""
        now = self._clock()
        if self._last_at is not None and (now - self._last_at) < self._cooldown_seconds:
            return False
        self._last_at = now
        return True
