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
        pytest.skip("node is required for frontend filename tests")
    return node


def test_frontend_default_merge_output_name_uses_local_date() -> None:
    # Given
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    helper = extract_js_function(app_js, "defaultMergeOutputName")
    script = "\n".join(
        [
            helper,
            "const names = [",
            "  defaultMergeOutputName(new Date(2026, 5, 14, 0, 5, 0)),",
            "  defaultMergeOutputName(new Date(2026, 0, 2, 23, 59, 59))",
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


def test_frontend_merge_output_placeholder_does_not_show_merged_output() -> None:
    # Given
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    # When / Then
    assert 'placeholder="merged_output.mp4"' not in index_html
    assert 'placeholder="YYYY-MM-DD.mp4"' in index_html
