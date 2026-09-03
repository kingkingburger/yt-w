"""병합 소스 파일 삭제 UI 계약 검증."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def read_merge_javascript() -> str:
    return "\n".join(
        Path("web", filename).read_text(encoding="utf-8")
        for filename in ("merge_files.js", "merge_sequence.js", "merge_jobs.js")
    )


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
    app_js = read_merge_javascript()
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    assert "deleteSourceGroup(${groupIdx}, event)" in app_js
    assert "deleteSourceFile('${safePath}', event)" in app_js
    assert "return deleteSourceFiles(selectedSourcePaths(), '선택한 영상');" in app_js
    assert 'id="btn-delete-selected"' in index_html
    assert "삭제한 파일은 복구할 수 없습니다" in app_js


def test_source_file_delete_calls_api_and_refreshes_list() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the source file delete frontend test")

    app_js = read_merge_javascript()
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
function mergeFileName(path) {{ return path.split('/').pop(); }}
{delete_function}
(async () => {{
  await deleteSourceFiles(['one.mp4', 'two.mp4'], '방송 묶음');
  await deleteSourceFiles(['merged/solo.mp4'], '선택한 영상');
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
    assert events[2:5] == [
        ["loadFiles", True],
        ["systemRefresh"],
        ["notify", "삭제 완료", "영상 파일 2개를 삭제했습니다", "ok"],
    ]
    assert events[0] == ["confirm", "방송 묶음 2개를 삭제할까요?\n삭제한 파일은 복구할 수 없습니다."]
    # 하나만 지울 때는 "선택한 영상" 같은 묶음 라벨이 아니라 파일 이름을 보여 준다.
    assert events[5] == ["confirm", '"solo.mp4" 파일을 삭제할까요?\n삭제한 파일은 복구할 수 없습니다.']
