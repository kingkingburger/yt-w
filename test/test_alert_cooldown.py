"""AlertCooldown 값 객체 테스트 — 쿨다운 창 내 1회 통과 로직 검증."""

import pytest

from src.yt_monitor.monitoring.cooldown import AlertCooldown


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

    def test_clock_returning_zero_does_not_short_circuit(self):
        """clock이 0.0을 반환해도 sentinel과 구분되어 쿨다운이 정상 적용된다.

        과거 _last_at=0.0 sentinel은 falsy 단락으로 cooldown 분기를 건너뛰어,
        clock이 0.0을 돌려주면 두 번째 호출도 통과로 잘못 처리될 위험이 있었다.
        """
        clock = iter([0.0, 1.0])
        cooldown = AlertCooldown(cooldown_seconds=60.0, clock=lambda: next(clock))

        assert cooldown.try_acquire() is True
        # 1초만 경과 — 쿨다운 60초 안이므로 False여야 한다
        assert cooldown.try_acquire() is False
