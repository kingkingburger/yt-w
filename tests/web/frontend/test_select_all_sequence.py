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


def test_merge_page_exposes_select_all_and_deselect_all_controls() -> None:
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    source_title = index_html.index('<div class="card-title">소스 파일</div>')
    select_all = index_html.index(
        'id="btn-select-all" onclick="selectAllFiles()"'
    )
    sequence_title = index_html.index('<div class="card-title">합치기 순서</div>')
    deselect_all = index_html.index(
        'id="btn-deselect-all" onclick="deselectAllFiles()"'
    )
    sequence_body = index_html.index('<div class="card-body stack">', sequence_title)

    assert source_title < select_all < sequence_title
    assert sequence_title < deselect_all < sequence_body


def test_frontend_select_all_keeps_part_files_compact_and_deselect_all_clears() -> None:
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
            "colorForGroup",
            "inferPartGroup",
            "getPartInfo",
            "getPartRangeLabel",
            "buildFileGroups",
            "selectAllFiles",
            "deselectAllFiles",
            "getSequencePartBlock",
            "buildSequenceRows",
            "formatPartRangeName",
            "sequenceRowName",
        ]
    )

    script = f"""
const GROUP_COLORS = ['#e6a04d', '#6fb7ff'];
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
const rows = buildSequenceRows();
const selected = {{
  sequence: [...state.sequence],
  rows: rows.map(row => [row.start, row.end, sequenceRowName(row)])
}};
deselectAllFiles();
console.log(JSON.stringify({{
  selected,
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
        "selected": {
            "sequence": [
                "live/channel/channel_20260514_025824_part000.mp4",
                "live/channel/channel_20260514_025824_part001.mp4",
                "live/channel/channel_20260514_025824_part002.mp4",
                "live/channel/loose_video.mp4",
            ],
            "rows": [
                [0, 2, "20260514_025824 - part 000-002.mp4"],
                [3, 3, "loose_video.mp4"],
            ],
        },
        "cleared": {"sequence": [], "selectedPaths": []},
    }
