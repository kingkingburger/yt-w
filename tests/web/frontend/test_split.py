"""영상 나누기 화면과 프런트엔드 계약 검증."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def test_split_tab_contains_interval_and_equal_part_controls():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert 'data-tab="split"' in html
    assert 'id="panel-split"' in html
    assert 'id="split-interval-hours"' in html
    assert 'id="split-parts"' in html
    assert "2등분" in html
    assert "3등분" in html


def test_split_tab_contains_search_and_upload_controls():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert 'id="split-file-search"' in html
    assert 'id="split-upload-input"' in html
    assert 'onclick="chooseSplitUpload()"' in html
    assert "PC 영상 업로드" in html


def test_split_file_search_matches_name_and_path():
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the frontend search test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    match = re.search(
        r"function filterSplitFiles\([^)]*\) \{.*?^\}",
        app_js,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    script = f"""
{match.group(0)}
const files = [
  {{ name: 'long-broadcast.mp4', path: 'merged/long-broadcast.mp4' }},
  {{ name: 'clip.mp4', path: 'uploads/travel/clip.mp4' }}
];
console.log(JSON.stringify({{
  byName: filterSplitFiles(files, 'BROADCAST').map(file => file.path),
  byPath: filterSplitFiles(files, 'TRAVEL').map(file => file.path),
  all: filterSplitFiles(files, '  ').length
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "byName": ["merged/long-broadcast.mp4"],
        "byPath": ["uploads/travel/clip.mp4"],
        "all": 2,
    }


def test_split_file_list_reuses_merge_part_group_ui():
    app_js = Path("web/app.js").read_text(encoding="utf-8")

    assert "splitGroupOpen: new Set()" in app_js
    assert "buildFileGroups(filteredFiles)" in app_js
    assert "function toggleSplitGroup(groupIdx)" in app_js
    assert 'class="file-group-head split-file-group-head"' in app_js


def test_file_selection_controls_use_custom_visual_marks():
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    css = Path("web/app.css").read_text(encoding="utf-8")

    assert app_js.count('class="selection-control selection-checkbox"') == 2
    assert 'class="selection-control selection-radio"' in app_js
    assert 'class="selection-mark" aria-hidden="true"' in app_js
    assert ".selection-control input:focus-visible + .selection-mark" in css
    assert ".selection-checkbox input:indeterminate + .selection-mark::after" in css
    assert ".selection-radio input:checked + .selection-mark::after" in css


def test_split_frontend_javascript_is_valid():
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the frontend syntax test")

    result = subprocess.run(
        [node, "--check", "web/app.js"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
