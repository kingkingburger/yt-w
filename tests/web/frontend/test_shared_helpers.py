"""화면 공용 헬퍼(빈 상태 마크업, 응답 오류 처리) 계약 검증."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND_JS_FILES = (
    "app_core.js",
    "channels.js",
    "merge_files.js",
    "merge_sequence.js",
    "merge_jobs.js",
    "split.js",
    "youtube_upload.js",
    "download.js",
    "app.js",
)


def read_frontend_javascript() -> str:
    return "\n".join(
        Path("web", filename).read_text(encoding="utf-8")
        for filename in FRONTEND_JS_FILES
    )


def extract_js_arrow_constant(source: str, name: str, terminator: str) -> str:
    """`const 이름 = ...` 화살표 선언을 종료 표시까지 잘라낸다."""
    match = re.search(
        rf"const {name} = .*?^{re.escape(terminator)}",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name} 선언을 찾지 못했습니다"
    return match.group(0)


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the shared helper frontend tests")
    return node


def run_node_script(script: str) -> object:
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_empty_state_renders_icon_title_and_optional_action() -> None:
    app_js = read_frontend_javascript()
    empty_state = extract_js_arrow_constant(app_js, "emptyState", "</div>`;")

    script = f"""
{empty_state}
console.log(JSON.stringify({{
  withoutAction: emptyState({{
    icon: '▦',
    title: '아직 합치기 작업이 없어요',
    sub: '실행하면 진행 상황이 표시됩니다',
  }}),
  withAction: emptyState({{
    icon: '+',
    title: '아직 등록된 채널이 없어요',
    sub: '채널을 추가해 주세요',
    action: '<button class="btn primary">+ 첫 채널 추가하기</button>',
  }}),
}}));
"""
    rendered = run_node_script(script)

    assert '<div class="empty">' in rendered["withoutAction"]
    assert '<div class="empty-icon">▦</div>' in rendered["withoutAction"]
    assert (
        '<div class="empty-title">아직 합치기 작업이 없어요</div>'
        in rendered["withoutAction"]
    )
    assert (
        '<div class="empty-sub">실행하면 진행 상황이 표시됩니다</div>'
        in rendered["withoutAction"]
    )
    assert "<button" not in rendered["withoutAction"]
    assert (
        '<button class="btn primary">+ 첫 채널 추가하기</button>'
        in rendered["withAction"]
    )


def test_throw_if_response_failed_prefers_server_detail() -> None:
    app_js = read_frontend_javascript()
    guard = extract_js_arrow_constant(app_js, "throwIfResponseFailed", "};")

    script = f"""
{guard}
const messageOf = (promise) => promise.then(() => 'resolved', error => error.message);
Promise.all([
  messageOf(throwIfResponseFailed({{ ok: true }})),
  messageOf(throwIfResponseFailed({{
    ok: false,
    json: async () => ({{ detail: '채널을 찾을 수 없습니다' }}),
  }})),
  messageOf(throwIfResponseFailed({{ ok: false, json: async () => ({{}}) }})),
  messageOf(throwIfResponseFailed(
    {{ ok: false, json: async () => {{ throw new SyntaxError('not json'); }} }},
    'YouTube 업로드 취소를 요청하지 못했습니다.',
  )),
]).then(messages => console.log(JSON.stringify(messages)));
"""

    assert run_node_script(script) == [
        "resolved",
        "채널을 찾을 수 없습니다",
        "요청을 처리하지 못했습니다",
        "YouTube 업로드 취소를 요청하지 못했습니다.",
    ]


def test_list_panels_share_the_empty_state_helper() -> None:
    app_js = read_frontend_javascript()

    assert app_js.count("host.innerHTML = emptyState({") == 10
    # 목록 로더 7개가 응답 상태 확인을 공용 헬퍼로 넘기면서 6 → 13이 됐다.
    assert app_js.count("await throwIfResponseFailed(") == 13
