"""Merge ordering regression tests."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import src.yt_monitor.media.merge as video_merger
from src.yt_monitor.media.merge import MergeJobManager


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
    raise AssertionError(f"function {name} was not closed")


def test_merge_submit_preserves_requested_input_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The backend must pass the ordered request inputs through to ffmpeg."""
    root = tmp_path / "downloads"
    root.mkdir()
    for name in ["10.mp4", "2.mp4", "1.mp4"]:
        (root / name).write_bytes(b"video")

    thread_args = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.args = args

        def start(self):
            thread_args.append(self.args)

    monkeypatch.setattr(video_merger.threading, "Thread", FakeThread)

    requested = ["10.mp4", "2.mp4", "1.mp4"]
    job = MergeJobManager(root).submit(requested, "out.mp4", "concat")

    assert job.inputs == requested
    assert len(thread_args) == 1
    absolute_inputs = thread_args[0][1]
    assert absolute_inputs == [(root / name).resolve() for name in requested]


def test_merge_rejects_sibling_prefix_path_escape(tmp_path: Path):
    """A sibling path that shares the root prefix must not pass containment."""
    root = tmp_path / "downloads"
    sibling = tmp_path / "downloads_evil"
    root.mkdir()
    sibling.mkdir()
    (root / "a.mp4").write_bytes(b"video")
    (sibling / "b.mp4").write_bytes(b"video")

    with pytest.raises(ValueError, match="잘못된 입력 경로"):
        MergeJobManager(root).submit(
            ["a.mp4", "../downloads_evil/b.mp4"],
            "out.mp4",
            "concat",
        )


def test_frontend_name_sort_uses_natural_filename_order():
    """The merge sequence name-sort must order 1, 2, 10 naturally."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend sort regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    sort_function = extract_js_function(app_js, "sortSequenceByName")

    script = f"""
const state = {{
  sequence: [
    'clips/10.mp4',
    'clips/2.mp4',
    'archive/1.mp4',
    'clips/1.mp4'
  ]
}};
function renderSequence() {{}}
{sort_function}
sortSequenceByName();
console.log(JSON.stringify(state.sequence));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        "archive/1.mp4",
        "clips/1.mp4",
        "clips/2.mp4",
        "clips/10.mp4",
    ]


def test_frontend_detects_contiguous_part_runs_for_file_drag():
    """Dragging a part clip should carry the contiguous part run with it."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend drag regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helpers = "\n".join(
        extract_js_function(app_js, name)
        for name in [
            "splitMergePath",
            "inferPartGroup",
            "getPartInfo",
            "getPartRun",
        ]
    )

    script = f"""
const state = {{
  files: [
    {{ path: 'show_part_001.mp4' }},
    {{ path: 'show_part_002.mp4' }},
    {{ path: 'show_part_003.mp4' }},
    {{ path: 'show_part_005.mp4' }},
    {{ path: 'other_part_001.mp4' }}
  ]
}};
{helpers}
console.log(JSON.stringify(getPartRun('show_part_002.mp4')));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        "show_part_001.mp4",
        "show_part_002.mp4",
        "show_part_003.mp4",
    ]


def test_frontend_groups_part_runs_by_hash_like_token():
    """Hash-like tokens before part numbers should be the compact grouping key."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend drag regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helpers = "\n".join(
        extract_js_function(app_js, name)
        for name in [
            "splitMergePath",
            "mergeFileName",
            "inferPartGroup",
            "getPartInfo",
            "getPartRun",
            "getSequencePartBlock",
            "buildSequenceRows",
            "formatPartRangeName",
            "sequenceRowName",
        ]
    )

    script = f"""
const state = {{
  files: [
    {{ path: 'title_a1b2c3d4_part001.mp4' }},
    {{ path: 'renamed_a1b2c3d4_part002.mp4' }},
    {{ path: 'other_z9y8x7w6_part001.mp4' }}
  ],
  sequence: [
    'title_a1b2c3d4_part001.mp4',
    'renamed_a1b2c3d4_part002.mp4',
    'other_z9y8x7w6_part001.mp4'
  ],
  sequenceViewMode: 'compact'
}};
{helpers}
const rows = buildSequenceRows();
const fullRows = buildSequenceRows('full');
console.log(JSON.stringify({{
  run: getPartRun('renamed_a1b2c3d4_part002.mp4'),
  rows: rows.map(row => [row.start, row.end, sequenceRowName(row)]),
  fullRows: fullRows.map(row => [row.start, row.end, sequenceRowName(row)])
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "run": [
            "title_a1b2c3d4_part001.mp4",
            "renamed_a1b2c3d4_part002.mp4",
        ],
        "rows": [
            [0, 1, "a1b2c3d4 - part 001-002.mp4"],
            [2, 2, "other_z9y8x7w6_part001.mp4"],
        ],
        "fullRows": [
            [0, 0, "title_a1b2c3d4_part001.mp4"],
            [1, 1, "renamed_a1b2c3d4_part002.mp4"],
            [2, 2, "other_z9y8x7w6_part001.mp4"],
        ],
    }


def test_frontend_source_tree_groups_by_hash_token():
    """The source file tree should group part files by the hash/timestamp key."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend source tree regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helpers = "\n".join(
        extract_js_function(app_js, name)
        for name in [
            "splitMergePath",
            "mergeFileName",
            "colorForGroup",
            "inferPartGroup",
            "getPartInfo",
            "getPartRangeLabel",
            "buildFileGroups",
        ]
    )

    script = f"""
const GROUP_COLORS = ['#e6a04d', '#6fb7ff'];
{helpers}
const groups = buildFileGroups([
  {{ path: 'live/channel/channel_20260514_025824_part002.mp4', size_bytes: 1, mtime: 1 }},
  {{ path: 'live/channel/channel_20260514_025824_part000.mp4', size_bytes: 1, mtime: 1 }},
  {{ path: 'live/channel/channel_20260514_025824_part001.mp4', size_bytes: 1, mtime: 1 }},
  {{ path: 'live/channel/loose_video.mp4', size_bytes: 1, mtime: 1 }}
]);
console.log(JSON.stringify(groups.map(group => ({{
  name: group.name,
  partLabel: group.partLabel || '',
  paths: group.paths,
  firstFileName: mergeFileName(group.paths[0])
}}))));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        {
            "name": "20260514_025824",
            "partLabel": "part 000-002",
            "paths": [
                "live/channel/channel_20260514_025824_part000.mp4",
                "live/channel/channel_20260514_025824_part001.mp4",
                "live/channel/channel_20260514_025824_part002.mp4",
            ],
            "firstFileName": "channel_20260514_025824_part000.mp4",
        },
        {
            "name": "loose_video.mp4",
            "partLabel": "",
            "paths": ["live/channel/loose_video.mp4"],
            "firstFileName": "loose_video.mp4",
        },
    ]


def test_frontend_source_tree_hides_files_already_in_sequence():
    """The source tree should only show files not already staged for merge."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend source tree regression test")

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
        ]
    )

    script = f"""
const GROUP_COLORS = ['#e6a04d', '#6fb7ff'];
const state = {{
  files: [
    {{ path: 'live/channel/channel_20260514_025824_part000.mp4', size_bytes: 1, mtime: 1 }},
    {{ path: 'live/channel/channel_20260514_025824_part001.mp4', size_bytes: 1, mtime: 1 }},
    {{ path: 'live/channel/loose_video.mp4', size_bytes: 1, mtime: 1 }}
  ],
  sequence: [
    'live/channel/channel_20260514_025824_part001.mp4',
    'live/channel/loose_video.mp4'
  ]
}};
{helpers}
const groups = buildFileGroups(availableSourceFiles());
console.log(JSON.stringify(groups.map(group => ({{
  name: group.name,
  paths: group.paths
}}))));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        {
            "name": "20260514_025824",
            "paths": ["live/channel/channel_20260514_025824_part000.mp4"],
        },
    ]


def test_frontend_moves_contiguous_sequence_part_block_together():
    """Dragging a sequence item in a consecutive part run should move the run."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the frontend drag regression test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helpers = "\n".join(
        extract_js_function(app_js, name)
        for name in [
            "splitMergePath",
            "inferPartGroup",
            "getPartInfo",
            "getSequencePartBlock",
            "moveSequenceBlock",
        ]
    )

    script = f"""
const state = {{
  sequence: [
    'intro.mp4',
    'show_part_001.mp4',
    'show_part_002.mp4',
    'show_part_003.mp4',
    'tail.mp4'
  ]
}};
{helpers}
const block = getSequencePartBlock(2);
moveSequenceBlock(block.start, block.end, state.sequence.length);
console.log(JSON.stringify(state.sequence));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        "intro.mp4",
        "tail.mp4",
        "show_part_001.mp4",
        "show_part_002.mp4",
        "show_part_003.mp4",
    ]
