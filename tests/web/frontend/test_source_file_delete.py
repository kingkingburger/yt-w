"""병합 소스 파일 삭제 UI 계약 검증."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def extract_js_function(source: str, name: str) -> str:
    async_marker = f"async function {name}("
    marker = async_marker if async_marker in source else f"function {name}("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Function {name} not found")


def test_source_list_renders_file_and_group_delete_actions() -> None:
    app_js = Path("web/app.js").read_text(encoding="utf-8")

    assert "deleteSourceGroup(${groupIdx}, event)" in app_js
    assert "deleteSourceFile('${safePath}', event)" in app_js
    assert "삭제한 파일은 복구할 수 없습니다" in app_js


def test_source_file_delete_calls_api_and_refreshes_list() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the source file delete frontend test")

    app_js = Path("web/app.js").read_text(encoding="utf-8")
    delete_function = extract_js_function(app_js, "deleteSourceFiles")
    script = f"""
const API = '';
const events = [];
function confirm(message) {{ events.push(['confirm', message]); return true; }}
async function fetch(url, options) {{
  events.push(['fetch', url, options]);
  return {{ ok: true, json: async () => ({{ count: 2 }}) }};
}}
async function loadFiles(refresh) {{ events.push(['loadFiles', refresh]); }}
function systemRefresh() {{ events.push(['systemRefresh']); }}
function notify(title, message, kind) {{ events.push(['notify', title, message, kind]); }}
{delete_function}
(async () => {{
  await deleteSourceFiles(['one.mp4', 'two.mp4'], '방송 묶음');
  console.log(JSON.stringify(events));
}})();
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    events = json.loads(result.stdout)
    request = events[1]
    assert request[0:2] == ["fetch", "/api/files"]
    assert request[2]["method"] == "DELETE"
    assert json.loads(request[2]["body"]) == {"paths": ["one.mp4", "two.mp4"]}
    assert events[2:] == [
        ["loadFiles", True],
        ["systemRefresh"],
        ["notify", "삭제 완료", "소스 파일 2개를 삭제했습니다", "ok"],
    ]
