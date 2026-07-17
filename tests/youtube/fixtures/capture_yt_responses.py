"""yt-dlp 실제 응답을 캡처해서 골든 픽스처로 저장한다.

사용법:
    python tests/youtube/fixtures/capture_yt_responses.py

수동 실행 도구. yt-dlp/YouTube가 변경되어 라이브 감지가 깨졌을 때
다시 실행해서 픽스처를 갱신한다. diff로 어떤 필드가 변했는지 확인.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yt_dlp


OUTPUT_DIR: Path = Path(__file__).parent / "youtube_responses"

CHANNELS: Dict[str, str] = {
    "lofigirl": "https://www.youtube.com/@LofiGirl",
    "ted": "https://www.youtube.com/@TED",
}

STRATEGY_SUFFIX: Dict[str, str] = {
    "streams_tab": "/streams",
    "channel_page": "",
    "live_endpoint": "/live",
}

_MAX_ENTRIES_PER_RESPONSE: int = 10

# 라이브 감지에 쓰이는 필드만 픽스처에 남긴다. 나머지(thumbnails, tags, description,
# format 메타 등)는 _parse_info가 보지 않으므로 잘라낸다. yt-dlp가 새 필드명으로
# 라이브를 표시하기 시작하면, 그때 다시 캡처해 keys 목록에 추가한다.
_ROOT_KEEP_KEYS: Tuple[str, ...] = (
    "id",
    "title",
    "is_live",
    "live_status",
    "_type",
)
_ENTRY_KEEP_KEYS: Tuple[str, ...] = (
    "id",
    "title",
    "is_live",
    "live_status",
    "url",
    "_type",
)


def _minimize_entry(entry: Any) -> Any:
    if not isinstance(entry, dict):
        return entry
    return {key: entry[key] for key in _ENTRY_KEEP_KEYS if key in entry}


def _minimize(info: Dict[str, Any]) -> Dict[str, Any]:
    minimized: Dict[str, Any] = {
        key: info[key] for key in _ROOT_KEEP_KEYS if key in info
    }
    entries = info.get("entries")
    if isinstance(entries, list):
        minimized["entries"] = [
            _minimize_entry(entry) for entry in entries[:_MAX_ENTRIES_PER_RESPONSE]
        ]
    return minimized


def _capture(channel_url: str, suffix: str) -> Optional[Dict[str, Any]]:
    target_url = channel_url.rstrip("/") + suffix
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target_url, download=False)
        if info is None:
            return None
        sanitized: Dict[str, Any] = ydl.sanitize_info(info)
    return _minimize(sanitized)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for channel_name, channel_url in CHANNELS.items():
        for strategy_name, url_suffix in STRATEGY_SUFFIX.items():
            label = f"{channel_name}_{strategy_name}"
            print(f"capturing {label} ...")
            try:
                info = _capture(channel_url, url_suffix)
            except Exception as error:
                print(f"  FAILED: {error}")
                continue
            output_path = OUTPUT_DIR / f"{label}.json"
            output_path.write_text(
                json.dumps(info, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            print(f"  saved {output_path.name}")


if __name__ == "__main__":
    main()
