"""SplitStrategy 테스트 — split_mode 문자열 해석과 split_seconds 계산."""

import pytest

from src.yt_monitor.media.split_strategy import (
    NoSplit,
    SizeSplit,
    TimeSplit,
    make_split_strategy,
)


class TestTimeSplit:
    def test_split_seconds_converts_minutes(self):
        assert TimeSplit(minutes=30).split_seconds() == 1800

    def test_non_positive_minutes_raise(self):
        for minutes in (0, -5):
            with pytest.raises(ValueError):
                TimeSplit(minutes=minutes)


class TestSizeSplit:
    def test_split_seconds_with_default_bitrate(self):
        """size 100MB × 8 / 5Mbps = 160초."""
        assert SizeSplit(megabytes=100).split_seconds() == 160

    def test_split_seconds_with_custom_bitrate(self):
        """size 500MB × 8 / 10Mbps = 400초."""
        assert (
            SizeSplit(megabytes=500, estimated_bitrate_mbps=10).split_seconds() == 400
        )

    def test_zero_megabytes_raises(self):
        with pytest.raises(ValueError):
            SizeSplit(megabytes=0)


class TestNoSplit:
    def test_no_split_seconds_is_none(self):
        """NoSplit은 분할하지 않음 — split_seconds는 의미 없음."""
        assert NoSplit().split_seconds() is None


class TestMakeSplitStrategy:
    """문자열 → SplitStrategy 팩토리."""

    def test_none_returns_no_split(self):
        strategy = make_split_strategy("none", time_minutes=30, size_mb=500)
        assert isinstance(strategy, NoSplit)

    def test_time_returns_time_split(self):
        strategy = make_split_strategy("time", time_minutes=30, size_mb=500)
        assert isinstance(strategy, TimeSplit)
        assert strategy.split_seconds() == 1800

    def test_size_returns_size_split(self):
        strategy = make_split_strategy("size", time_minutes=30, size_mb=100)
        assert isinstance(strategy, SizeSplit)
        assert strategy.split_seconds() == 160

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid split_mode"):
            make_split_strategy("invalid", time_minutes=30, size_mb=500)
