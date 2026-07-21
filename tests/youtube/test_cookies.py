"""브라우저 프로필 기반 yt-dlp 인증 옵션 테스트."""

from src.yt_monitor.youtube import cookies as cookie_options


class TestLocalBrowserCookies:
    def test_local_uses_firefox_by_default(self, monkeypatch):
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)
        monkeypatch.delenv("YT_COOKIE_BROWSER", raising=False)

        options = cookie_options.get_cookie_options()

        assert options == {
            "remote_components": ["ejs:github"],
            "cookiesfrombrowser": ("firefox",),
        }

    def test_local_uses_configured_browser(self, monkeypatch):
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: False)
        monkeypatch.setenv("YT_COOKIE_BROWSER", "chrome")

        options = cookie_options.get_cookie_options()

        assert options == {
            "remote_components": ["ejs:github"],
            "cookiesfrombrowser": ("chrome",),
        }


class TestDockerBrowserCookies:
    def test_firefox_profile_is_preferred_with_runtime_options(
        self, monkeypatch
    ):
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

    def test_docker_without_profile_uses_no_browser_cookie_source(self, monkeypatch):
        monkeypatch.setattr(cookie_options, "_is_docker", lambda: True)
        monkeypatch.setattr(cookie_options, "_get_firefox_profile_path", lambda: "")
        monkeypatch.setattr(cookie_options, "_POT_PROVIDER_URL", "")

        options = cookie_options.get_cookie_options()

        assert options == {
            "remote_components": ["ejs:github"],
            "js_runtimes": {"node": {}},
        }
