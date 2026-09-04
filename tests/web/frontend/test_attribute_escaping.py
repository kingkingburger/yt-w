"""파일 목록 행의 속성 값 이스케이프 계약 검증.

escapeHtml은 텍스트 노드 직렬화라 `&`, `<`, `>`만 바꾸고 따옴표는 그대로 둔다.
속성 자리에는 escapeHtmlAttribute만 쓰고, 인라인 핸들러는 경로를 문자열로 보간하지 않고
this.value / this.dataset.path로 읽는다.
"""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import pytest

StartTag = tuple[str, dict[str, Optional[str]]]

ATTRIBUTE_ESCAPED_JS_FILES = (
    "merge_files.js",
    "merge_sequence.js",
    "split.js",
    "library.js",
    "youtube_upload.js",
)
HOSTILE_FILE_NAME = 'zz" onmouseover="alert(1).mp4'
HOSTILE_FILE_PATH = f"uploads/{HOSTILE_FILE_NAME}"


def read_web_javascript(*filenames: str) -> str:
    return "\n".join(
        Path("web", filename).read_text(encoding="utf-8") for filename in filenames
    )


def extract_js_function(source: str, name: str) -> str:
    marker = f"function {name}("
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


def extract_escape_attribute_helper() -> str:
    core_js = Path("web/app_core.js").read_text(encoding="utf-8")
    marker = "const escapeHtmlAttribute ="
    start = core_js.index(marker)
    end = core_js.index(";\n", start) + 1
    return core_js[start:end]


class StartTagCollector(HTMLParser):
    """마크업의 시작 태그와 (엔티티를 푼) 속성값을 순서대로 모은다."""

    def __init__(self) -> None:
        super().__init__()
        self.start_tags: list[StartTag] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, Optional[str]]]
    ) -> None:
        self.start_tags.append((tag, dict(attrs)))


def collect_start_tags(markup: str) -> list[StartTag]:
    collector = StartTagCollector()
    collector.feed(markup)
    return collector.start_tags


def find_start_tag(
    start_tags: list[StartTag], tag: str, class_name: Optional[str] = None
) -> dict[str, Optional[str]]:
    for found_tag, attributes in start_tags:
        if found_tag != tag:
            continue
        if class_name is None or class_name in (attributes.get("class") or "").split():
            return attributes
    raise AssertionError(f"<{tag} class={class_name}> not found")


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the attribute escaping frontend tests")
    return node


def test_attribute_positions_never_use_the_text_escaper() -> None:
    source = read_web_javascript(*ATTRIBUTE_ESCAPED_JS_FILES)

    assert re.findall(r'="\$\{escapeHtml\(', source) == []
    # 경로를 JS 문자열로 보간하던 우회(따옴표만 역슬래시 처리)는 더 쓰지 않는다.
    assert "escapeHtml(f.path).replace(" not in source
    assert "escapeHtml(file.path).replace(" not in source


def test_merge_and_split_rows_keep_hostile_names_inside_attributes() -> None:
    node = require_node()
    render_source_row = extract_js_function(
        read_web_javascript("merge_files.js"), "renderSourceFileRow"
    )
    render_split_row = extract_js_function(
        read_web_javascript("split.js"), "renderSplitFileRow"
    )
    script = f"""
const state = {{ selectedPaths: new Set(), splitSelectedPath: null }};
const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
{extract_escape_attribute_helper()}
const mergeFileName = (path) => path.split('/').pop();
const fmtBytes = () => '1MB';
const fmtAge = () => '방금 전';
{render_source_row}
{render_split_row}
const file = {{
  path: {json.dumps(HOSTILE_FILE_PATH)},
  name: {json.dumps(HOSTILE_FILE_NAME)},
  size_bytes: 1,
  mtime: 1,
}};
console.log(JSON.stringify({{
  merge: renderSourceFileRow(file),
  split: renderSplitFileRow(file),
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rendered = json.loads(result.stdout)

    # 텍스트 노드에는 원문이 남아도 되지만, 파서가 읽은 속성 목록에 튀어나오면 안 된다.
    for markup in rendered.values():
        for _tag, attributes in collect_start_tags(markup):
            assert "onmouseover" not in attributes

    merge_tags = collect_start_tags(rendered["merge"])
    merge_label = find_start_tag(merge_tags, "label")
    merge_input = find_start_tag(merge_tags, "input")
    merge_name = find_start_tag(merge_tags, "div", class_name="file-name")
    merge_button = find_start_tag(merge_tags, "button")
    assert merge_label["data-path"] == HOSTILE_FILE_PATH
    assert merge_label["ondragstart"] == "fileDragStart(event, this.dataset.path)"
    assert merge_input["value"] == HOSTILE_FILE_PATH
    assert merge_input["onchange"] == "toggleFileSelect(this.value, this.checked)"
    assert merge_name["title"] == HOSTILE_FILE_NAME
    assert merge_button["data-path"] == HOSTILE_FILE_PATH
    assert merge_button["onclick"] == "deleteSourceFile(this.dataset.path, event)"

    split_tags = collect_start_tags(rendered["split"])
    split_input = find_start_tag(split_tags, "input")
    split_name = find_start_tag(split_tags, "div", class_name="file-name")
    assert split_input["value"] == HOSTILE_FILE_PATH
    assert split_input["onchange"] == "selectSplitFile(this.value)"
    assert split_name["title"] == HOSTILE_FILE_PATH
