"""ffmpeg 세그먼트 분할 명령 빌더 — 순수 함수만 있음 (subprocess 없음).

입력: yt-dlp가 반환한 info dict + 출력 패턴 + 분할 간격(초).
출력: subprocess.run에 그대로 넘길 수 있는 커맨드 리스트.

테스트는 dict → list 변환만 검증하므로 subprocess나 yt-dlp mock 없이 가능.
"""

from typing import Any, Dict, List


def build_ffmpeg_headers(info: Dict[str, Any]) -> List[str]:
    """yt-dlp info의 http_headers를 ffmpeg -headers 포맷으로 변환한다."""
    http_headers = info.get("http_headers", {})
    if not http_headers:
        return []
    header_str = "".join(f"{k}: {v}\r\n" for k, v in http_headers.items())
    return ["-headers", header_str]


def _build_dual_stream_command(
    info: Dict[str, Any],
    output_pattern: str,
    split_seconds: int,
) -> List[str]:
    """비디오+오디오 분리된 requested_formats 경우."""
    video = info["requested_formats"][0]
    audio = info["requested_formats"][1]

    return [
        "ffmpeg",
        *build_ffmpeg_headers(video),
        "-i",
        video["url"],
        *build_ffmpeg_headers(audio),
        "-i",
        audio["url"],
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(split_seconds),
        "-reset_timestamps",
        "1",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        output_pattern,
    ]


def _build_single_stream_command(
    info: Dict[str, Any],
    output_pattern: str,
    split_seconds: int,
) -> List[str]:
    """단일 스트림(url 필드) 경우."""
    return [
        "ffmpeg",
        *build_ffmpeg_headers(info),
        "-i",
        info["url"],
        "-c",
        "copy",
        "-f",
        "segment",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-segment_time",
        str(split_seconds),
        "-reset_timestamps",
        "1",
        output_pattern,
    ]


def build_segment_command(
    info: Dict[str, Any],
    output_pattern: str,
    split_seconds: int,
) -> List[str]:
    """yt-dlp info를 기반으로 ffmpeg 세그먼트 분할 커맨드를 조립한다.

    requested_formats가 있으면 dual-stream, 아니면 url 필드로 single-stream.
    """
    if "requested_formats" in info:
        return _build_dual_stream_command(info, output_pattern, split_seconds)
    if "url" in info:
        return _build_single_stream_command(info, output_pattern, split_seconds)
    raise ValueError("info에 'url' 또는 'requested_formats' 키가 필요합니다")
