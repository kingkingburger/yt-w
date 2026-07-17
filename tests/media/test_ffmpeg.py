"""ffmpeg_command 순수 함수 테스트 — subprocess 없이 dict → list 변환만 검증."""

import pytest

from src.yt_monitor.media.ffmpeg import (
    build_ffmpeg_headers,
    build_segment_command,
)


class TestBuildFfmpegHeaders:
    """build_ffmpeg_headers — yt-dlp info의 http_headers를 ffmpeg -headers 포맷으로."""

    def test_empty_when_headers_are_missing_or_empty(self):
        for info in ({}, {"url": "x"}, {"http_headers": {}}):
            assert build_ffmpeg_headers(info) == []

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


class TestBuildSegmentCommandSingleStream:
    """단일 스트림(url 필드) — 하나의 -i로 처리."""

    def test_builds_complete_command_with_headers_before_input(self):
        info = {
            "url": "https://direct.example.com/stream",
            "http_headers": {"User-Agent": "x"},
        }
        command = build_segment_command(info, "/out/%03d.mp4", split_seconds=600)

        assert command == [
            "ffmpeg",
            "-headers",
            "User-Agent: x\r\n",
            "-i",
            "https://direct.example.com/stream",
            "-c",
            "copy",
            "-f",
            "segment",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-segment_time",
            "600",
            "-reset_timestamps",
            "1",
            "/out/%03d.mp4",
        ]


class TestBuildSegmentCommandDualStream:
    """video+audio 분리된 requested_formats — 두 개의 -i."""

    def test_builds_complete_command_with_per_input_headers(self):
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
        command = build_segment_command(info, "/out/%03d.mp4", split_seconds=1800)

        assert command == [
            "ffmpeg",
            "-headers",
            "User-Agent: v-agent\r\n",
            "-i",
            "https://video.example.com",
            "-headers",
            "User-Agent: a-agent\r\n",
            "-i",
            "https://audio.example.com",
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            "1800",
            "-reset_timestamps",
            "1",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "/out/%03d.mp4",
        ]


class TestBuildSegmentCommandInvalid:
    def test_raises_when_no_url_or_requested_formats(self):
        with pytest.raises(ValueError, match="url"):
            build_segment_command({}, "/out/%03d.mp4", split_seconds=600)
