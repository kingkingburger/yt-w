"""yt-dlp 실제 응답(골든 픽스처)으로 라이브 감지 회귀를 막는다.

골든 픽스처는 test/fixtures/youtube_responses/ 에 저장된 yt-dlp 실제 응답이다.
손으로 쓴 mock과 달리 yt-dlp가 *실제로* 내려준 응답 모양을 그대로 보존하므로,
69d79c8("Docker 라이브 감지 누락 보완")처럼 "응답 모양이 우리 가정과 달라
못 잡았다" 류의 회귀를 즉시 잡는다.

픽스처 갱신:
    python test/fixtures/capture_yt_responses.py

yt-dlp/YouTube 변경으로 이 테스트가 깨지면, 먼저 픽스처를 재캡처하고
diff로 어떤 필드가 바뀌었는지 확인한다.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from src.yt_monitor.youtube.client import YouTubeClient


_FIXTURES_DIR: Path = Path(__file__).parent / "fixtures" / "youtube_responses"

_URL_SUFFIX_TO_STRATEGY: Tuple[Tuple[str, str], ...] = (
    ("/streams", "streams_tab"),
    ("/live", "live_endpoint"),
)


def _load_fixture(fixture_name: str) -> Optional[Dict[str, Any]]:
    fixture_path = _FIXTURES_DIR / f"{fixture_name}.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _build_fake_extract_info(channel_key: str) -> Callable[..., Any]:
    """채널 키에 대해 url 접미사별 픽스처를 반환하는 fake extract_info."""

    def fake_extract_info(target_url: str, download: bool = False) -> Any:
        for suffix, strategy_name in _URL_SUFFIX_TO_STRATEGY:
            if target_url.endswith(suffix):
                return _load_fixture(f"{channel_key}_{strategy_name}")
        return _load_fixture(f"{channel_key}_channel_page")

    return fake_extract_info


def _patch_yt_dlp_with_channel(channel_key: str):
    """yt_dlp.YoutubeDL를 픽스처 기반 fake로 패치하는 context manager 생성."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    instance.extract_info.side_effect = _build_fake_extract_info(channel_key)
    return patch("yt_dlp.YoutubeDL", return_value=instance)


class TestLiveDetectionGoldenFixtures:
    """실제 yt-dlp 응답으로 라이브 감지 컨트랙트를 못 박는다."""

    @pytest.fixture
    def youtube_client(self, initialized_logger) -> YouTubeClient:
        return YouTubeClient()

    def test_lofigirl_detected_as_live_via_live_endpoint(
        self, youtube_client: YouTubeClient
    ):
        """캡처 시점의 LofiGirl 라이브 응답에서 video_id를 추출해야 한다.

        실제로 캡처된 응답에서 /streams와 채널 페이지에는 live_status가 비어 있고,
        /live 루트 메타데이터에만 is_live=True가 있다. 69d79c8 보강 전 코드는
        이 케이스를 놓쳤다.
        """
        live_endpoint_response = _load_fixture("lofigirl_live_endpoint")
        expected_video_id = live_endpoint_response["id"]

        with _patch_yt_dlp_with_channel("lofigirl"):
            is_live, stream_info = youtube_client.check_if_live(
                "https://www.youtube.com/@LofiGirl"
            )

        assert is_live is True
        assert stream_info is not None
        assert stream_info.video_id == expected_video_id

    def test_ted_not_detected_as_live(self, youtube_client: YouTubeClient):
        """TED 채널은 라이브 안 하는 채널 — (False, None) 반환 보장."""
        with _patch_yt_dlp_with_channel("ted"):
            is_live, stream_info = youtube_client.check_if_live(
                "https://www.youtube.com/@TED"
            )

        assert is_live is False
        assert stream_info is None
