"""AlertCooldown 값 객체 테스트 — 쿨다운 창 내 1회 통과 로직 검증."""

import pytest

from src.yt_monitor.alert_cooldown import AlertCooldown


class TestAlertCooldown:
    """쿨다운 창 내에서 최대 1번만 try_acquire가 True를 반환한다."""

    def test_first_acquire_succeeds(self):
        """첫 호출은 항상 True."""
        clock = iter([100.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(clock))

        assert cooldown.try_acquire() is True

    def test_second_acquire_within_window_fails(self):
        """쿨다운 창 내 재호출은 False."""
        clock = iter([100.0, 130.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(clock))

        assert cooldown.try_acquire() is True
        assert cooldown.try_acquire() is False

    def test_acquire_after_window_succeeds_again(self):
        """쿨다운 경과 후 재호출은 True."""
        clock = iter([100.0, 161.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(clock))

        assert cooldown.try_acquire() is True
        assert cooldown.try_acquire() is True

    def test_repeated_acquires_within_window_all_fail(self):
        """창 내 반복 호출은 첫 번째만 True, 나머지 모두 False."""
        times = iter([100.0, 105.0, 110.0, 115.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(times))

        assert cooldown.try_acquire() is True
        assert cooldown.try_acquire() is False
        assert cooldown.try_acquire() is False
        assert cooldown.try_acquire() is False

    def test_boundary_exact_cooldown_elapsed_succeeds(self):
        """정확히 쿨다운만큼 경과 시 통과 (경계 포함)."""
        clock = iter([100.0, 160.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(clock))

        assert cooldown.try_acquire() is True
        assert cooldown.try_acquire() is True

    def test_default_clock_uses_time_module(self):
        """clock 주입이 없어도 동작한다 (time.time 기본)."""
        cooldown = AlertCooldown(cooldown_seconds=60.0)
        assert cooldown.try_acquire() is True
        # 즉시 재호출은 쿨다운에 걸려야 함
        assert cooldown.try_acquire() is False

    def test_invalid_cooldown_raises(self):
        """음수 쿨다운은 허용되지 않는다."""
        with pytest.raises(ValueError):
            AlertCooldown(cooldown_seconds=-1.0)
