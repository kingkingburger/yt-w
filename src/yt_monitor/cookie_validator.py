"""쿠키 유효성 검증 — 결과만 반환, 알림 책임 없음.

호출자가 CookieValidationResult를 받아 필요하면 알림을 전송한다.
테스트에서 CookieValidator 인스턴스를 직접 만들어 격리 가능.
"""

import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional

from .cookie_options import _COOKIE_SOURCE_PATH, get_cookie_options


_TEST_VIDEO_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_DEFAULT_CACHE_TTL_SECONDS: float = 300.0


@dataclass(frozen=True)
class CookieValidationResult:
    """쿠키 유효성 검증 결과."""

    valid: bool
    has_cookies: bool
    message: str
    checked_at: float
    cached: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CookieValidator:
    """쿠키 유효성 검증 — 상태(캐시)를 캡슐화한 인스턴스 클래스.

    알림이나 외부 부수효과 없음. 결과는 CookieValidationResult로 반환.
    """

    def __init__(
        self,
        cookie_source_path: Optional[str] = None,
        cache_ttl_seconds: float = _DEFAULT_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ):
        self._cookie_source_path: str = cookie_source_path or _COOKIE_SOURCE_PATH
        self._cache_ttl_seconds: float = cache_ttl_seconds
        self._clock: Callable[[], float] = clock
        self._lock: threading.Lock = threading.Lock()
        self._cached_valid: Optional[bool] = None
        self._checked_at: float = 0.0

    def invalidate_cache(self) -> None:
        """캐시를 초기화해 다음 validate()가 실제 검사를 수행하게 한다."""
        with self._lock:
            self._cached_valid = None
            self._checked_at = 0.0

    def validate(self, force: bool = False) -> CookieValidationResult:
        """쿠키 유효성을 검사하고 결과를 반환한다.

        Args:
            force: True이면 캐시 무시
        """
        now = self._clock()

        with self._lock:
            if not force and self._cached_valid is not None:
                if (now - self._checked_at) < self._cache_ttl_seconds:
                    return CookieValidationResult(
                        valid=self._cached_valid,
                        has_cookies=os.path.exists(self._cookie_source_path),
                        message=(
                            "쿠키 유효"
                            if self._cached_valid
                            else "쿠키 만료됨 — 브라우저에서 다시 내보내세요"
                        ),
                        checked_at=self._checked_at,
                        cached=True,
                    )

        if not os.path.exists(self._cookie_source_path):
            self._store_result(valid=False, now=now)
            return CookieValidationResult(
                valid=False,
                has_cookies=False,
                message="cookies.txt 파일이 없습니다",
                checked_at=now,
                cached=False,
            )

        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "socket_timeout": 15,
                **get_cookie_options(),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(_TEST_VIDEO_URL, download=False)

            if info and info.get("title"):
                self._store_result(valid=True, now=now)
                return CookieValidationResult(
                    valid=True,
                    has_cookies=True,
                    message="쿠키 유효",
                    checked_at=now,
                    cached=False,
                )

            self._store_result(valid=False, now=now)
            return CookieValidationResult(
                valid=False,
                has_cookies=True,
                message="쿠키 만료됨 — 브라우저에서 다시 내보내세요",
                checked_at=now,
                cached=False,
            )

        except Exception as error:
            self._store_result(valid=False, now=now)
            error_text = str(error)
            if "Sign in to confirm" in error_text or "cookies" in error_text.lower():
                message = "쿠키 만료됨 — 브라우저에서 다시 내보내세요"
            else:
                message = f"쿠키 검증 실패: {error_text[:100]}"
            return CookieValidationResult(
                valid=False,
                has_cookies=True,
                message=message,
                checked_at=now,
                cached=False,
            )

    def _store_result(self, valid: bool, now: float) -> None:
        with self._lock:
            self._cached_valid = valid
            self._checked_at = now


_default_validator: CookieValidator = CookieValidator()


def validate_cookies(force: bool = False) -> Dict[str, Any]:
    """모듈 레벨 기본 validator를 경유한 레거시 진입점."""
    return _default_validator.validate(force).to_dict()


def invalidate_cookie_cache() -> None:
    """모듈 레벨 기본 validator 캐시를 초기화한다."""
    _default_validator.invalidate_cache()
