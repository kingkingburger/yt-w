"""영상 관리 화면 계약 검증 — 폴더별 묶음, 검색 범위 안의 전체 선택, 삭제 연결."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

LIBRARY_JS_FILES = ("app_core.js", "merge_files.js", "merge_sequence.js", "split.js", "library.js")


def read_library_javascript() -> str:
    return "\n".join(
        Path("web", filename).read_text(encoding="utf-8") for filename in LIBRARY_JS_FILES
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


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the library frontend tests")
    return node


def run_node(script: str) -> object:
    result = subprocess.run(
        [require_node(), "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def library_script_prelude(app_js: str) -> str:
    return "\n".join(
        [
            """
const state = {
  files: [
    { path: 'merged/final.mp4', name: 'final.mp4', size_bytes: 300, mtime: 3 },
    { path: 'live/채널/rec_part001.mp4', name: 'rec_part001.mp4', size_bytes: 100, mtime: 2 },
    { path: 'root.mp4', name: 'root.mp4', size_bytes: 50, mtime: 1 },
    { path: 'live/채널/rec_part000.mp4', name: 'rec_part000.mp4', size_bytes: 100, mtime: 0 },
  ],
  librarySelectedPaths: new Set(),
  librarySearchQuery: '',
  libraryGroupOpen: new Set(),
  libraryGroups: [],
};
const events = [];
function renderLibrary() { events.push('render'); }
function deleteSourceFiles(paths, label) { events.push(['delete', paths, label]); }
""",
            extract_js_function(app_js, "splitMergePath"),
            extract_js_function(app_js, "mergeFileName"),
            extract_js_function(app_js, "filterSplitFiles"),
            extract_js_function(app_js, "buildLibraryGroups"),
            extract_js_function(app_js, "libraryVisibleFiles"),
            extract_js_function(app_js, "selectAllLibraryFiles"),
            extract_js_function(app_js, "toggleLibraryGroupSelect"),
            extract_js_function(app_js, "deleteLibraryGroup"),
            extract_js_function(app_js, "deleteSelectedLibraryFiles"),
        ]
    )


def test_library_tab_is_last_menu_item_with_management_controls() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    nav_start = html.index('<nav class="nav"')
    nav_end = html.index("</nav>", nav_start)
    nav = html[nav_start:nav_end]
    panel_start = html.index('<section id="panel-library"')
    panel_end = html.index("</section>\n      </section>", panel_start)
    panel = html[panel_start:panel_end]

    assert nav.rindex("data-tab=") == nav.index('data-tab="library"')
    assert 'aria-controls="panel-library"' in nav
    assert "영상 관리" in nav
    assert 'id="library-file-count"' in panel
    assert 'id="btn-library-select-all" onclick="selectAllLibraryFiles()"' in panel
    assert (
        'id="btn-library-delete-selected" onclick="deleteSelectedLibraryFiles()" disabled'
        in panel
    )
    assert 'id="library-file-search"' in panel
    assert 'oninput="setLibrarySearch(this.value)"' in panel
    assert 'class="file-list" id="library-file-list"' in panel
    assert html.index('src="/static/youtube_upload.js"') < html.index(
        'src="/static/library.js"'
    ) < html.index('src="/static/download.js"')


def test_library_tab_loads_shared_file_list() -> None:
    app_core_js = Path("web/app_core.js").read_text(encoding="utf-8")
    merge_files_js = Path("web/merge_files.js").read_text(encoding="utf-8")

    assert "if (tab === 'library') { loadFiles(); }" in app_core_js
    assert "librarySelectedPaths: new Set()," in app_core_js
    assert "renderLibrary();" in extract_js_function(merge_files_js, "loadFiles")


def test_library_groups_files_by_directory_with_summed_size() -> None:
    app_js = read_library_javascript()
    output = run_node(
        f"""
{library_script_prelude(app_js)}
console.log(JSON.stringify(buildLibraryGroups(state.files).map(group => [
  group.id, group.name, group.paths, group.sizeBytes,
])));
"""
    )

    assert output == [
        ["", "/", ["root.mp4"], 50],
        ["live/채널/", "live/채널", ["live/채널/rec_part001.mp4", "live/채널/rec_part000.mp4"], 200],
        ["merged/", "merged", ["merged/final.mp4"], 300],
    ]


def test_library_select_all_stays_inside_search_and_toggles_off() -> None:
    app_js = read_library_javascript()
    output = run_node(
        f"""
{library_script_prelude(app_js)}
state.librarySearchQuery = 'part';
selectAllLibraryFiles();
const filtered = [...state.librarySelectedPaths];
state.librarySearchQuery = '';
selectAllLibraryFiles();
const everything = [...state.librarySelectedPaths];
selectAllLibraryFiles();
console.log(JSON.stringify({{ filtered, everything, cleared: [...state.librarySelectedPaths], events }}));
"""
    )

    assert output == {
        "filtered": ["live/채널/rec_part001.mp4", "live/채널/rec_part000.mp4"],
        "everything": [
            "live/채널/rec_part001.mp4",
            "live/채널/rec_part000.mp4",
            "merged/final.mp4",
            "root.mp4",
        ],
        "cleared": [],
        "events": ["render", "render", "render"],
    }


def test_library_group_and_selection_delete_reuse_shared_delete_path() -> None:
    app_js = read_library_javascript()
    output = run_node(
        f"""
{library_script_prelude(app_js)}
state.libraryGroups = buildLibraryGroups(state.files);
toggleLibraryGroupSelect(1, true);
deleteSelectedLibraryFiles();
deleteLibraryGroup(2, {{ preventDefault() {{ events.push('preventDefault'); }}, stopPropagation() {{ events.push('stopPropagation'); }} }});
console.log(JSON.stringify(events));
"""
    )

    assert output == [
        "render",
        ["delete", ["live/채널/rec_part001.mp4", "live/채널/rec_part000.mp4"], "선택한 영상"],
        "preventDefault",
        "stopPropagation",
        ["delete", ["merged/final.mp4"], '"merged" 폴더의 영상'],
    ]


def test_library_rows_escape_attributes_and_wire_delete_button() -> None:
    library_js = Path("web/library.js").read_text(encoding="utf-8")
    row_function = extract_js_function(library_js, "renderLibraryFileRow")

    assert "const safePathAttribute = escapeHtmlAttribute(file.path);" in row_function
    assert 'onchange="toggleLibraryFile(this.value, this.checked)"' in row_function
    assert 'onclick="deleteLibraryFile(this.dataset.path, event)"' in row_function
    assert 'class="file-row child library-file-row' in row_function
    assert 'class="file-group-head library-file-group-head"' in library_js


def test_library_card_fills_tab_height_and_drops_drag_grip_column() -> None:
    css = Path("web/app.css").read_text(encoding="utf-8")
    card_block = css[css.index("#panel-library > .library-card {") :].split("}")[0]
    row_block = css[css.index(".library-file-row {") :].split("}")[0]

    assert "flex: 1;" in card_block
    assert "flex-direction: column;" in card_block
    assert "grid-template-columns: 18px minmax(0, 1fr) auto auto 24px;" in row_block
    assert ".youtube-upload-file-row .file-delete-btn" in css
    assert ".library-file-tools" in css
