"""목록 로딩 실패가 빈 상태로 위장되지 않는지 검증한다."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# (파일, 로더 함수, 실패를 그려야 하는 host id)
LIST_LOADERS = (
    ("download.js", "loadRecentFiles", ("recent-files",)),
    ("channels.js", "loadChannels", ("channel-list",)),
    ("channels.js", "loadRecentRecordings", ("recent-recordings",)),
    (
        "merge_files.js",
        "loadFiles",
        ("merge-file-list", "split-file-list", "youtube-upload-file-list"),
    ),
    ("merge_jobs.js", "loadJobs", ("merge-jobs",)),
    ("split.js", "loadSplitJobs", ("split-jobs",)),
    ("youtube_upload.js", "loadYouTubeUploadJobs", ("youtube-upload-jobs",)),
)


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the load failure frontend tests")
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


def extract_js_function(source: str, name: str) -> str:
    """`async function 이름(...) { ... }` 선언을 닫는 중괄호까지 잘라낸다."""
    match = re.search(
        rf"^(?:async )?function {name}\(.*?^\}}",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name} 선언을 찾지 못했습니다"
    return match.group(0)


def extract_js_arrow_function(source: str, name: str) -> str:
    """`const 이름 = (...) => { ... };` 선언을 닫는 중괄호까지 잘라낸다."""
    match = re.search(
        rf"^const {name} = .*?^\}};",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name} 선언을 찾지 못했습니다"
    return match.group(0)


def read_frontend_file(filename: str) -> str:
    return Path("web", filename).read_text(encoding="utf-8")


@pytest.mark.parametrize(("filename", "loader", "host_ids"), LIST_LOADERS)
def test_list_loader_reports_failure_instead_of_staying_silent(
    filename: str, loader: str, host_ids: tuple[str, ...]
) -> None:
    """실패를 삼키면 화면은 "아직 없어요"라고 거짓말한다."""
    module_source = read_frontend_file(filename)
    body = extract_js_function(module_source, loader)

    assert "catch (e) {}" not in body
    assert "catch (error) {}" not in body
    assert "throwIfResponseFailed(" in body, f"{loader}가 응답 상태를 확인하지 않습니다"
    assert "renderLoadFailure(" in body
    for host_id in host_ids:
        assert host_id in module_source, f"{loader}가 {host_id}에 실패를 알리지 않습니다"


def test_render_load_failure_shows_title_and_reason_escaped() -> None:
    app_core_js = read_frontend_file("app_core.js")
    render_load_failure = extract_js_arrow_function(app_core_js, "renderLoadFailure")

    script = f"""
const hosts = {{ 'recent-files': {{ innerHTML: '' }} }};
const $ = (id) => hosts[id] || null;
const escapeHtml = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
{render_load_failure}
renderLoadFailure('recent-files', '최근 받은 영상을 불러오지 못했어요',
  new Error('<img src=x> 서버가 응답하지 않습니다'));
const withReason = hosts['recent-files'].innerHTML;
renderLoadFailure('recent-files', '최근 받은 영상을 불러오지 못했어요', undefined);
const withoutReason = hosts['recent-files'].innerHTML;
renderLoadFailure('없는-호스트', '제목', new Error('무시된다'));
console.log(JSON.stringify({{ withReason, withoutReason }}));
"""
    rendered = run_node_script(script)

    assert "최근 받은 영상을 불러오지 못했어요" in rendered["withReason"]
    assert "&lt;img src=x&gt; 서버가 응답하지 않습니다" in rendered["withReason"]
    assert "<img src=x>" not in rendered["withReason"]
    assert "empty-icon-alert" in rendered["withReason"]
    assert "잠시 후 다시 시도해 주세요" in rendered["withoutReason"]


def test_failure_icon_is_visually_distinct_from_empty_icon() -> None:
    """빈 상태와 실패 상태가 같은 회색 아이콘이면 구분이 되지 않는다."""
    app_css = Path("web/app.css").read_text(encoding="utf-8")

    assert ".empty-icon-alert {" in app_css
    alert_block = app_css[app_css.index(".empty-icon-alert {") :].split("}")[0]
    assert "var(--warn-tint)" in alert_block
    assert "var(--warn-line)" in alert_block
    assert "var(--warn)" in alert_block


def test_shared_helper_is_declared_before_the_screens_that_use_it() -> None:
    index_html = Path("web/index.html").read_text(encoding="utf-8")
    order = [
        index_html.index(f'/static/{filename}')
        for filename in ("app_core.js", "channels.js", "merge_files.js", "download.js")
    ]

    assert order == sorted(order)
