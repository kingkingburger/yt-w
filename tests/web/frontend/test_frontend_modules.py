"""프런트엔드 모듈 경계와 classic script 조합 계약 검증."""

import shutil
import subprocess
from pathlib import Path

import pytest

RUNTIME_JS_FILES = (
    "app_core.js",
    "merge_output_name.js",
    "merge_download_directory.js",
    "channels.js",
    "merge_files.js",
    "merge_sequence.js",
    "merge_jobs.js",
    "split.js",
    "youtube_upload.js",
    "library.js",
    "download.js",
    "palette.js",
    "app.js",
)


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the frontend module tests")
    return node


def test_runtime_scripts_are_loaded_in_dependency_order() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    positions = [
        html.index(f'src="/static/{filename}"')
        for filename in RUNTIME_JS_FILES
    ]

    assert positions == sorted(positions)


def test_domain_modules_stay_bounded_and_app_is_boot_only() -> None:
    line_counts = {
        filename: len(Path("web", filename).read_text(encoding="utf-8").splitlines())
        for filename in RUNTIME_JS_FILES
    }

    assert line_counts["app.js"] <= 50
    assert all(count <= 500 for filename, count in line_counts.items() if filename != "app.js")


def test_runtime_scripts_parse_as_one_classic_script_scope() -> None:
    source = "\n".join(
        Path("web", filename).read_text(encoding="utf-8")
        for filename in ("palette_boot.js", *RUNTIME_JS_FILES)
    )
    result = subprocess.run(
        [
            require_node(),
            "-e",
            "new Function(require('fs').readFileSync(0, 'utf8'));",
        ],
        input=source,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.stderr == ""
