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
    raise AssertionError(f"function {name} was not closed")


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for frontend filename tests")
    return node


def read_merge_output_name_source() -> str:
    output_name_js = Path("web/merge_output_name.js")
    if output_name_js.exists():
        return output_name_js.read_text(encoding="utf-8")
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    return extract_js_function(app_js, "defaultMergeOutputName")


def test_frontend_default_merge_output_name_uses_local_date() -> None:
    # Given
    helpers = read_merge_output_name_source()
    script = "\n".join(
        [
            helpers,
            "const names = [",
            "  defaultMergeOutputName([], new Date(2026, 5, 14, 0, 5, 0)),",
            "  defaultMergeOutputName([], new Date(2026, 0, 2, 23, 59, 59))",
            "];",
            'console.log(names.join("\\n"));',
        ]
    )

    # When
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    # Then
    assert result.stdout.splitlines() == ["2026-06-14.mp4", "2026-01-02.mp4"]


def test_frontend_merge_output_name_uses_earliest_source_date() -> None:
    # Given
    helpers = read_merge_output_name_source()
    script = "\n".join(
        [
            helpers,
            "const output = defaultMergeOutputName([",
            "  'live/channel/channel_0610_part000.mp4',",
            "  'live/channel/channel_2026-06-09_part001.mp4',",
            "  'live/channel/no_date_part002.mp4'",
            "], new Date(2026, 5, 15));",
            "console.log(output);",
        ]
    )

    # When
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    # Then
    assert result.stdout.strip() == "2026-06-09.mp4"


def test_frontend_add_paths_updates_default_merge_output_name() -> None:
    # Given
    helpers = read_merge_output_name_source()
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    add_paths = extract_js_function(app_js, "addPathsToSequence")
    script = "\n".join(
        [
            "const output = { value: '', dataset: {} };",
            "const state = { sequence: [], selectedPaths: new Set() };",
            "function $(id) { return id === 'merge-output' ? output : null; }",
            "function renderFileList() {}",
            "function renderSequence() {}",
            helpers,
            add_paths,
            "addPathsToSequence([",
            "  'live/channel/channel_0610_part000.mp4',",
            "  'live/channel/channel_20260608_part001.mp4'",
            "]);",
            "console.log(output.value);",
        ]
    )

    # When
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    # Then
    assert result.stdout.strip() == "2026-06-08.mp4"


def test_frontend_merge_output_placeholder_does_not_show_merged_output() -> None:
    # Given
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    # When / Then
    assert 'placeholder="merged_output.mp4"' not in index_html
    assert 'placeholder="YYYY-MM-DD.mp4"' in index_html
