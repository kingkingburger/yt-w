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


def test_frontend_select_all_keeps_part_files_compact_by_default() -> None:
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
            "toggleSelectAll",
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
toggleSelectAll();
const rows = buildSequenceRows();
console.log(JSON.stringify({{
  sequence: state.sequence,
  rows: rows.map(row => [row.start, row.end, sequenceRowName(row)])
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
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
    }
