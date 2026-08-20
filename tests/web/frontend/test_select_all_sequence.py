import json
import shutil
import subprocess
from pathlib import Path

import pytest


def extract_js_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    for idx in range(brace, len(source)):
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f"Function {name} not found")


def test_merge_page_exposes_select_send_delete_and_clear_controls() -> None:
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    source_title = index_html.index('<div class="card-title">합칠 영상 고르기</div>')
    select_all = index_html.index(
        'id="btn-select-all" onclick="selectAllFiles()"'
    )
    delete_selected = index_html.index(
        'id="btn-delete-selected" onclick="deleteSelectedSourceFiles()"'
    )
    send_selected = index_html.index(
        'id="btn-send-selected" onclick="sendSelectedFilesToSequence()"'
    )
    sequence_title = index_html.index('<div class="card-title">순서 정하고 합치기</div>')
    deselect_all = index_html.index(
        'id="btn-deselect-all" onclick="deselectAllFiles()"'
    )
    sequence_body = index_html.index('<div class="card-body stack">', sequence_title)

    assert source_title < select_all < delete_selected < send_selected < sequence_title
    assert sequence_title < deselect_all < sequence_body


def test_frontend_selection_waits_for_send_and_keeps_part_files_compact() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the frontend select-all regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helpers = "\n".join(
        extract_js_function(app_js, name)
        for name in [
            "splitMergePath",
            "mergeFileName",
            "availableSourceFiles",
            "inferPartGroup",
            "getPartInfo",
            "getPartRangeLabel",
            "buildFileGroups",
            "selectedSourcePaths",
            "selectAllFiles",
            "sendSelectedFilesToSequence",
            "deselectAllFiles",
            "addPathsToSequence",
            "getSequencePartBlock",
            "buildSequenceRows",
            "formatPartRangeName",
            "sequenceRowName",
        ]
    )

    script = f"""
const state = {{
  files: [
    {{ path: 'live/channel/channel_20260514_025824_part002.mp4', size_bytes: 1, mtime: 1 }},
    {{ path: 'live/channel/loose_video.mp4', size_bytes: 1, mtime: 1 }},
    {{ path: 'live/channel/channel_20260514_025824_part000.mp4', size_bytes: 1, mtime: 1 }},
    {{ path: 'live/channel/channel_20260514_025824_part001.mp4', size_bytes: 1, mtime: 1 }}
  ],
  selectedPaths: new Set(),
  sequence: [],
  sequenceViewMode: 'compact'
}};
function refreshDefaultMergeOutputName() {{}}
function renderFileList() {{}}
function renderSequence() {{}}
{helpers}
selectAllFiles();
const checked = {{
  sequence: [...state.sequence],
  selectedPaths: [...state.selectedPaths]
}};
sendSelectedFilesToSequence();
const rows = buildSequenceRows();
const sent = {{
  sequence: [...state.sequence],
  selectedPaths: [...state.selectedPaths],
  rows: rows.map(row => [row.start, row.end, sequenceRowName(row)])
}};
deselectAllFiles();
console.log(JSON.stringify({{
  checked,
  sent,
  cleared: {{
    sequence: state.sequence,
    selectedPaths: [...state.selectedPaths]
  }}
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "checked": {
            "sequence": [],
            "selectedPaths": [
                "live/channel/channel_20260514_025824_part000.mp4",
                "live/channel/channel_20260514_025824_part001.mp4",
                "live/channel/channel_20260514_025824_part002.mp4",
                "live/channel/loose_video.mp4",
            ],
        },
        "sent": {
            "sequence": [
                "live/channel/channel_20260514_025824_part000.mp4",
                "live/channel/channel_20260514_025824_part001.mp4",
                "live/channel/channel_20260514_025824_part002.mp4",
                "live/channel/loose_video.mp4",
            ],
            "selectedPaths": [],
            "rows": [
                [0, 2, "channel_20260514_025824 · part 000-002.mp4"],
                [3, 3, "loose_video.mp4"],
            ],
        },
        "cleared": {"sequence": [], "selectedPaths": []},
    }
