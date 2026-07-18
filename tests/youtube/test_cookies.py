"""cookie_options.get_cookie_options 분기 테스트.

핵심 회귀: 로컬 환경에서 cookies.txt가 있으면 yt-dlp가 원본을 덮어쓰지 못하도록
임시 복사본 경로를 cookiefile로 전달해야 한다.
"""

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def reload_cookie_options(monkeypatch, tmp_path):
    """모듈 레벨 상수 _COOKIE_SOURCE_PATH를 격리하기 위해 모듈을 재import한다."""
    cookie_path = tmp_path / "cookies.txt"
    monkeypatch.setenv("YT_COOKIES_FILE", str(cookie_path))
    monkeypatch.delenv("YT_POT_PROVIDER_URL", raising=False)
    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)

    import src.yt_monitor.youtube.cookies as cookie_options
    importlib.reload(cookie_options)
    yield cookie_options, cookie_path
    temp_path = cookie_options._cookie_temp_path
    if temp_path and os.path.exists(temp_path):
        os.unlink(temp_path)


class TestLocalCookieFileBranch:
    """로컬 환경에서 cookies.txt가 존재할 때 동작."""

    def test_local_cookies_use_writable_temp_copy(
        self, reload_cookie_options, monkeypatch, tmp_path
    ):
        """로컬에서 cookies.txt가 있으면 임시 복사본 경로가 반환되어 원본이 보호된다."""
        cookie_options, cookie_path = reload_cookie_options
        cookie_path.write_text("# Netscape cookies\n", encoding="utf-8")

        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)

        options = cookie_options.get_cookie_options()

        assert "cookiefile" in options
        # 반환된 경로는 원본과 달라야 한다 (임시 복사본)
        assert options["cookiefile"] != str(cookie_path)
        # 임시 파일도 실제 존재해야 한다
        assert cookie_options.os.path.exists(options["cookiefile"])

    def test_local_no_cookies_falls_back_to_browser(
        self, reload_cookie_options, monkeypatch
    ):
        """로컬에서 cookies.txt가 없으면 cookiesfrombrowser로 폴백."""
        cookie_options, _ = reload_cookie_options
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)
        monkeypatch.setenv("YT_COOKIE_BROWSER", "firefox")

        options = cookie_options.get_cookie_options()

        assert "cookiesfrombrowser" in options
        assert options["cookiesfrombrowser"][0] == "firefox"
        assert "cookiefile" not in options

    def test_refresh_replaces_and_removes_stale_temp_copy(
        self, reload_cookie_options, monkeypatch
    ):
        cookie_options, cookie_path = reload_cookie_options
        cookie_path.write_text("old-cookie", encoding="utf-8")
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)

        first_path = cookie_options.get_cookie_options()["cookiefile"]
        source_mtime = os.path.getmtime(cookie_path)
        cookie_path.write_text("new-cookie", encoding="utf-8")
        os.utime(cookie_path, (source_mtime + 10, source_mtime + 10))

        second_path = cookie_options.get_cookie_options()["cookiefile"]

        assert second_path != first_path
        assert not os.path.exists(first_path)
        assert Path(second_path).read_text(encoding="utf-8") == "new-cookie"

    def test_copy_failure_falls_back_without_leaking_temp_file(
        self, reload_cookie_options, monkeypatch
    ):
        cookie_options, cookie_path = reload_cookie_options
        cookie_path.write_text("cookie", encoding="utf-8")
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)
        monkeypatch.setattr(
            cookie_options.shutil,
            "copy2",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")),
        )

        options = cookie_options.get_cookie_options()

        assert "cookiefile" not in options
        assert cookie_options._cookie_temp_path == ""


class TestDockerCookieBranches:
    def test_firefox_profile_is_preferred_with_runtime_options(
        self, reload_cookie_options, monkeypatch
    ):
        cookie_options, _cookie_path = reload_cookie_options
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: True)
        monkeypatch.setattr(
            cookie_options,
            "_get_firefox_profile_path",
            lambda: "/app/firefox_profile",
        )
        monkeypatch.setattr(
            cookie_options,
            "_POT_PROVIDER_URL",
            "http://pot-provider:4416",
        )

        options = cookie_options.get_cookie_options()

        assert options == {
            "remote_components": ["ejs:github"],
            "js_runtimes": {"node": {}},
            "extractor_args": {
                "youtubepot-bgutilhttp": {
                    "base_url": ["http://pot-provider:4416"]
                }
            },
            "cookiesfrombrowser": (
                "firefox",
                "/app/firefox_profile",
                None,
                None,
            ),
        }

    def test_cookie_file_is_docker_fallback_when_profile_is_missing(
        self, reload_cookie_options, monkeypatch
    ):
        cookie_options, cookie_path = reload_cookie_options
        cookie_path.write_text("cookie", encoding="utf-8")
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: True)
        monkeypatch.setattr(cookie_options, "_get_firefox_profile_path", lambda: "")

        options = cookie_options.get_cookie_options()

        assert options["js_runtimes"] == {"node": {}}
        assert Path(options["cookiefile"]).read_text(encoding="utf-8") == "cookie"
        assert "cookiesfrombrowser" not in options

    def test_docker_without_profile_or_file_uses_no_cookie_source(
        self, reload_cookie_options, monkeypatch
    ):
        cookie_options, _cookie_path = reload_cookie_options
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: True)
        monkeypatch.setattr(cookie_options, "_get_firefox_profile_path", lambda: "")

        options = cookie_options.get_cookie_options()

        assert options == {
            "remote_components": ["ejs:github"],
            "js_runtimes": {"node": {}},
        }
