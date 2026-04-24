"""CookieValidator 테스트 — 알림 책임 없이 결과만 반환한다."""

from unittest.mock import MagicMock, patch


from src.yt_monitor.cookie_validator import (
    CookieValidationResult,
    CookieValidator,
)


class TestCookieValidatorResult:
    """validate()가 CookieValidationResult를 반환한다."""

    def test_returns_invalid_when_file_missing(self, tmp_path):
        """cookies.txt 없으면 valid=False, has_cookies=False."""
        validator = CookieValidator(
            cookie_source_path=str(tmp_path / "no_cookies.txt"),
            clock=lambda: 1000.0,
        )

        result = validator.validate()

        assert result.valid is False
        assert result.has_cookies is False
        assert "없습니다" in result.message
        assert result.checked_at == 1000.0
        assert result.cached is False

    def test_returns_valid_when_ytdlp_returns_title(self, tmp_path):
        """yt-dlp 응답에 title이 있으면 valid=True."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "jNQXAC9IVRw", "title": "Me at the zoo",
        }

        validator = CookieValidator(
            cookie_source_path=str(cookies_file),
            clock=lambda: 2000.0,
        )

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = validator.validate()

        assert result.valid is True
        assert result.has_cookies is True
        assert result.checked_at == 2000.0
        assert result.cached is False

    def test_returns_invalid_when_title_missing(self, tmp_path):
        """yt-dlp가 title 없는 info를 반환하면 valid=False."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "jNQXAC9IVRw"}

        validator = CookieValidator(cookie_source_path=str(cookies_file))

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = validator.validate()

        assert result.valid is False
        assert "만료" in result.message

    def test_returns_invalid_on_ytdlp_exception(self, tmp_path):
        """yt-dlp 예외 시 valid=False + 적절한 메시지."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("Sign in to confirm your age")

        validator = CookieValidator(cookie_source_path=str(cookies_file))

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = validator.validate()

        assert result.valid is False
        assert "만료" in result.message


class TestCookieValidatorCache:
    """캐시 동작 검증."""

    def test_cache_hit_returns_cached_flag(self, tmp_path):
        """TTL 내 재호출은 cached=True, yt-dlp는 한 번만 호출."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "x", "title": "test"}

        # 두 번의 clock 호출 — 100초 차이 (TTL 300초 내)
        times = iter([100.0, 200.0])
        validator = CookieValidator(
            cookie_source_path=str(cookies_file),
            cache_ttl_seconds=300.0,
            clock=lambda: next(times),
        )

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            first = validator.validate()
            second = validator.validate()

        assert first.cached is False
        assert second.cached is True
        assert mock_ydl.extract_info.call_count == 1

    def test_cache_expires_after_ttl(self, tmp_path):
        """TTL 경과 후 재호출은 다시 실제 검사."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "x", "title": "test"}

        # 첫 호출 100초, 두 번째 500초 (TTL 300초 초과)
        times = iter([100.0, 500.0])
        validator = CookieValidator(
            cookie_source_path=str(cookies_file),
            cache_ttl_seconds=300.0,
            clock=lambda: next(times),
        )

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            validator.validate()
            second = validator.validate()

        assert second.cached is False
        assert mock_ydl.extract_info.call_count == 2

    def test_force_bypasses_cache(self, tmp_path):
        """force=True이면 캐시를 무시한다."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "x", "title": "test"}

        times = iter([100.0, 150.0])
        validator = CookieValidator(
            cookie_source_path=str(cookies_file),
            cache_ttl_seconds=300.0,
            clock=lambda: next(times),
        )

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            validator.validate()
            second = validator.validate(force=True)

        assert second.cached is False
        assert mock_ydl.extract_info.call_count == 2

    def test_invalidate_cache_clears_state(self, tmp_path):
        """invalidate_cache() 후에는 cached=False."""
        cookies_file = tmp_path / "cookies.txt"
        cookies_file.write_text("# Netscape HTTP Cookie File\n")

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: mock_ydl
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"id": "x", "title": "test"}

        validator = CookieValidator(
            cookie_source_path=str(cookies_file),
            clock=lambda: 1000.0,
        )

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            validator.validate()
            validator.invalidate_cache()
            result = validator.validate()

        assert result.cached is False


class TestCookieValidatorNoNotifierCoupling:
    """validator는 알림 책임이 없다 — 네트워크/IO 외에 side-effect 없음."""

    def test_validate_does_not_import_notifier(self, tmp_path):
        """validate가 discord_notifier 모듈을 건드리지 않는지 확인 (mock 인스턴스 사용)."""
        validator = CookieValidator(
            cookie_source_path=str(tmp_path / "missing.txt"),
            clock=lambda: 1000.0,
        )

        # notifier 모듈을 mock으로 대체해도 validator가 접근 안 해야 통과
        mock_notifier_module = MagicMock()
        with patch("src.yt_monitor.discord_notifier.get_notifier", mock_notifier_module):
            result = validator.validate()

        assert result.valid is False
        mock_notifier_module.assert_not_called()


class TestCookieValidationResult:
    """CookieValidationResult DTO 검증."""

    def test_to_dict_matches_legacy_format(self):
        """to_dict는 기존 validate_cookies 반환 딕셔너리 키와 호환."""
        result = CookieValidationResult(
            valid=True,
            has_cookies=True,
            message="쿠키 유효",
            checked_at=1234.5,
            cached=False,
        )

        d = result.to_dict()
        assert set(d.keys()) == {"valid", "has_cookies", "message", "checked_at", "cached"}
        assert d["valid"] is True
        assert d["checked_at"] == 1234.5


class TestLegacyShim:
    """validate_cookies() 모듈 함수와 invalidate_cookie_cache() 하위 호환."""

    def test_validate_cookies_returns_dict(self, tmp_path):
        """기존 코드가 쓰던 validate_cookies()가 딕셔너리 반환."""
        from src.yt_monitor.cookie_validator import invalidate_cookie_cache, validate_cookies

        invalidate_cookie_cache()

        with patch("src.yt_monitor.cookie_validator._default_validator") as mock_validator:
            mock_validator.validate.return_value = CookieValidationResult(
                valid=False, has_cookies=False, message="test", checked_at=0.0, cached=False,
            )
            result = validate_cookies()

        assert isinstance(result, dict)
        assert result["valid"] is False
