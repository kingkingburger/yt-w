"""ffmpeg_command 순수 함수 테스트 — subprocess 없이 dict → list 변환만 검증."""

import pytest

from src.yt_monitor.ffmpeg_command import (
    build_ffmpeg_headers,
    build_segment_command,
)


class TestBuildFfmpegHeaders:
    """build_ffmpeg_headers — yt-dlp info의 http_headers를 ffmpeg -headers 포맷으로."""

    def test_empty_when_no_headers(self):
        assert build_ffmpeg_headers({}) == []

    def test_empty_when_key_missing(self):
        assert build_ffmpeg_headers({"url": "x"}) == []

    def test_empty_when_headers_dict_empty(self):
        assert build_ffmpeg_headers({"http_headers": {}}) == []

    def test_formats_headers_correctly(self):
        info = {
            "http_headers": {
                "User-Agent": "Mozilla/5.0",
                "Cookie": "abc=123",
            }
        }
        result = build_ffmpeg_headers(info)

        assert len(result) == 2
        assert result[0] == "-headers"
        assert "User-Agent: Mozilla/5.0\r\n" in result[1]
        assert "Cookie: abc=123\r\n" in result[1]

    def test_single_header(self):
        info = {"http_headers": {"User-Agent": "test"}}
        assert build_ffmpeg_headers(info) == ["-headers", "User-Agent: test\r\n"]


class TestBuildSegmentCommandSingleStream:
    """단일 스트림(url 필드) — 하나의 -i로 처리."""

    def test_includes_url_and_segment_time(self):
        info = {"url": "https://direct.example.com/stream"}
        cmd = build_segment_command(info, "/out/part%03d.mp4", split_seconds=600)

        assert "ffmpeg" in cmd
        assert "https://direct.example.com/stream" in cmd
        assert "-segment_time" in cmd
        assert "600" in cmd
        assert "/out/part%03d.mp4" in cmd

    def test_headers_placed_before_input(self):
        info = {
            "url": "https://direct.example.com/stream",
            "http_headers": {"User-Agent": "x"},
        }
        cmd = build_segment_command(info, "/out/%03d.mp4", split_seconds=600)

        h_idx = cmd.index("-headers")
        i_idx = cmd.index("-i")
        assert h_idx < i_idx

    def test_includes_stream_mapping(self):
        info = {"url": "https://x.com/stream"}
        cmd = build_segment_command(info, "/out/%03d.mp4", split_seconds=600)
        joined = " ".join(cmd)
        assert "0:v:0" in joined
        assert "0:a:0" in joined


class TestBuildSegmentCommandDualStream:
    """video+audio 분리된 requested_formats — 두 개의 -i."""

    def test_includes_two_inputs(self):
        info = {
            "requested_formats": [
                {"url": "https://video.example.com"},
                {"url": "https://audio.example.com"},
            ]
        }
        cmd = build_segment_command(info, "/out/%03d.mp4", split_seconds=1800)

        assert cmd.count("-i") == 2
        assert "https://video.example.com" in cmd
        assert "https://audio.example.com" in cmd

    def test_each_input_has_its_own_headers(self):
        info = {
            "requested_formats": [
                {
                    "url": "https://video.example.com",
                    "http_headers": {"User-Agent": "v-agent"},
                },
                {
                    "url": "https://audio.example.com",
                    "http_headers": {"User-Agent": "a-agent"},
                },
            ]
        }
        cmd = build_segment_command(info, "/out/%03d.mp4", split_seconds=1800)

        headers_idx = [i for i, a in enumerate(cmd) if a == "-headers"]
        inputs_idx = [i for i, a in enumerate(cmd) if a == "-i"]

        assert len(headers_idx) == 2
        for h, i in zip(headers_idx, inputs_idx):
            assert h < i

    def test_maps_video_and_audio_streams(self):
        info = {
            "requested_formats": [
                {"url": "https://video.example.com"},
                {"url": "https://audio.example.com"},
            ]
        }
        cmd = build_segment_command(info, "/out/%03d.mp4", split_seconds=1800)
        joined = " ".join(cmd)
        assert "0:v:0" in joined
        assert "1:a:0" in joined


class TestBuildSegmentCommandInvalid:
    def test_raises_when_no_url_or_requested_formats(self):
        with pytest.raises(ValueError, match="url"):
            build_segment_command({}, "/out/%03d.mp4", split_seconds=600)
