"""YouTube 단일 계정 업로드 화면 계약 검증."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

YOUTUBE_UPLOAD_JS_FILES = ("app_core.js", "youtube_upload.js", "app.js")


def read_youtube_upload_javascript() -> str:
    return "\n".join(
        Path("web", filename).read_text(encoding="utf-8")
        for filename in YOUTUBE_UPLOAD_JS_FILES
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
        pytest.fail("node is required for the YouTube upload frontend tests")
    return node


def test_youtube_upload_tab_contains_single_account_controls() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    panel_start = html.index('<section id="panel-youtube-upload"')
    panel_end = html.index('<section id="panel-monitor"', panel_start)
    panel = html[panel_start:panel_end]

    assert 'data-tab="youtube-upload"' in html
    assert 'id="panel-youtube-upload"' in panel
    assert 'href="https://studio.youtube.com/"' in panel
    assert 'target="_blank" rel="noopener noreferrer"' in panel
    assert "YouTube 계정 바로가기" in panel
    assert 'id="btn-youtube-connect"' in panel
    assert 'id="btn-youtube-disconnect"' in panel
    assert 'id="youtube-oauth-message" role="status" aria-live="polite"' in panel
    assert 'id="youtube-upload-file-list"' in panel
    assert 'id="btn-youtube-select-all" onclick="selectAllYouTubeUploadFiles()"' in panel
    assert (
        'id="btn-youtube-delete-selected" onclick="deleteSelectedYouTubeUploadFiles()" disabled'
        in panel
    )
    assert 'id="youtube-upload-title"' in panel
    assert 'id="youtube-upload-description"' in panel
    assert 'id="youtube-upload-tags"' in panel
    assert 'id="youtube-upload-category"' in panel
    assert '<option value="22" selected>' in panel
    assert 'id="youtube-upload-made-for-kids"' in panel
    assert 'class="selection-control selection-checkbox youtube-kids-checkbox"' in panel
    assert 'class="selection-mark" aria-hidden="true"' in panel
    assert "비공개 · 고정" in panel
    assert 'id="youtube-upload-jobs"' in panel
    assert 'type="file"' not in panel


def test_download_is_first_sidebar_item() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    nav_start = html.index('<nav class="nav"')
    first_button_start = html.index('<button class="nav-btn', nav_start)
    first_button_end = html.index("</button>", first_button_start)

    assert 'data-tab="download"' in html[first_button_start:first_button_end]


def test_youtube_kids_checkbox_uses_studio_selection_mark() -> None:
    css = Path("web/app.css").read_text(encoding="utf-8")

    assert ".youtube-kids-control:has(input:checked)" in css
    assert ".selection-checkbox input:checked + .selection-mark::after" in css
    assert ".youtube-kids-control input {" not in css


def test_youtube_upload_javascript_targets_backend_contract() -> None:
    app_js = read_youtube_upload_javascript()

    assert "if (tab === 'youtube-upload')" in app_js
    assert "`${API}/api/youtube/oauth/status`" in app_js
    assert "`${API}/api/youtube/oauth/start`" in app_js
    assert "`${API}/api/youtube/oauth/connection`" in app_js
    assert app_js.count("`${API}/api/youtube/uploads`") == 2
    assert "`${API}/api/youtube/uploads/${encodeURIComponent(jobId)}/cancel`" in app_js
    assert "'X-YT-Monitor-Request': '1'" in app_js
    assert "headers: { ...YOUTUBE_MUTATION_HEADERS, 'Content-Type': 'application/json' }" in app_js
    for field in (
        "source,",
        "title,",
        "description:",
        "tags:",
        "category_id:",
        "made_for_kids:",
    ):
        assert field in app_js
    assert "state.activeTab === 'youtube-upload'" in app_js
    assert "loadYouTubeUploadJobs(); }, 3000" in app_js


def test_youtube_upload_file_filter_allows_only_server_video_directories() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    filter_function = extract_js_function(app_js, "filterYouTubeUploadFiles")
    script = f"""
{filter_function}
const files = [
  {{ path: 'merged/final.MP4' }},
  {{ path: 'split/clip.webm' }},
  {{ path: 'uploads/nested/movie.mov' }},
  {{ path: 'web_downloads/archive.mkv' }},
  {{ path: 'uploads/legacy.mpeg' }},
  {{ path: 'merged/audio.mp3' }},
  {{ path: 'split/voice.m4a' }},
  {{ path: 'uploads/unsupported.flv' }},
  {{ path: 'Merged/wrong-case.mp4' }},
  {{ path: '/merged/absolute.mp4' }},
  {{ path: 'merged/../outside.mp4' }},
  {{ path: 'merged/.hidden/clip.mp4' }},
  {{ path: ['uploads', 'windows', 'capture.ts'].join(String.fromCharCode(92)) }},
  {{ path: 'recordings/live.mp4' }},
  {{ path: 'root-video.mp4' }},
  {{ path: 'uploads/deceptive.mp4.mp3' }}
];
console.log(JSON.stringify(filterYouTubeUploadFiles(files).map(file => file.path)));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert json.loads(result.stdout) == [
        "merged/final.MP4",
        "split/clip.webm",
        "uploads/nested/movie.mov",
        "web_downloads/archive.mkv",
        "uploads/legacy.mpeg",
    ]


def test_youtube_upload_file_attributes_escape_quotes() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    marker = "const escapeHtmlAttribute ="
    start = app_js.index(marker)
    end = app_js.index(";\n", start) + 1
    escape_function = app_js[start:end]
    script = f"""
{escape_function}
console.log(escapeHtmlAttribute(`merged/\" onfocus=\"alert(1).mp4`));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.stdout.strip() == (
        "merged/&quot; onfocus=&quot;alert(1).mp4"
    )
    assert "const safePathAttribute = escapeHtmlAttribute(file.path);" in app_js
    assert "const safeNameAttribute = escapeHtmlAttribute(fileName);" in app_js


def youtube_selection_script_prelude(app_js: str) -> str:
    """체크 선택 계약을 검사하는 node 스크립트가 공통으로 쓰는 상태·스텁."""
    return "\n".join(
        [
            """
const state = {
  files: [
    {
      path: 'merged/침착맨_라이브_20260826_053736.mp4',
      name: '침착맨_라이브_20260826_053736.mp4',
    },
    { path: 'split/clip-1.mp4', name: 'clip-1.mp4' },
    { path: 'live/채널/recording.mp4', name: 'recording.mp4' },
  ],
  youtubeUploadSelectedPaths: new Set(),
};
const elements = {
  'youtube-upload-title': { value: '기존 제목', maxLength: 100 },
};
const events = [];
function $(id) { return elements[id]; }
function mergeFileName(path) { return path.split('/').pop(); }
function renderYouTubeUploadFileList() { events.push('render-list'); }
function renderYouTubeUploadReady() { events.push('render-ready'); }
function deleteSourceFiles(paths, label) { events.push(['delete', paths, label]); }
""",
            extract_js_function(app_js, "filterYouTubeUploadFiles"),
            extract_js_function(app_js, "youtubeUploadTargetPath"),
            extract_js_function(app_js, "fillYouTubeUploadTitle"),
            extract_js_function(app_js, "toggleYouTubeUploadFile"),
            extract_js_function(app_js, "selectAllYouTubeUploadFiles"),
            extract_js_function(app_js, "deleteSelectedYouTubeUploadFiles"),
        ]
    )


def test_youtube_upload_file_check_fills_title_only_when_it_becomes_the_single_choice() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    script = f"""
{youtube_selection_script_prelude(app_js)}
const snapshots = [];
const snapshot = (step) => snapshots.push({{
  step,
  selected: [...state.youtubeUploadSelectedPaths],
  target: youtubeUploadTargetPath(),
  title: elements['youtube-upload-title'].value,
}});
toggleYouTubeUploadFile('merged/침착맨_라이브_20260826_053736.mp4', true);
snapshot('check-first');
elements['youtube-upload-title'].value = '손으로 고친 제목';
toggleYouTubeUploadFile('split/clip-1.mp4', true);
snapshot('check-second');
toggleYouTubeUploadFile('merged/침착맨_라이브_20260826_053736.mp4', false);
snapshot('uncheck-first');
console.log(JSON.stringify({{ snapshots, events }}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = json.loads(result.stdout)

    assert output["snapshots"] == [
        {
            "step": "check-first",
            "selected": ["merged/침착맨_라이브_20260826_053736.mp4"],
            "target": "merged/침착맨_라이브_20260826_053736.mp4",
            "title": "침착맨_라이브_20260826",
        },
        {
            "step": "check-second",
            "selected": ["merged/침착맨_라이브_20260826_053736.mp4", "split/clip-1.mp4"],
            "target": None,
            "title": "손으로 고친 제목",
        },
        {
            "step": "uncheck-first",
            "selected": ["split/clip-1.mp4"],
            "target": "split/clip-1.mp4",
            "title": "손으로 고친 제목",
        },
    ]
    assert output["events"] == ["render-list", "render-ready"] * 3


def test_youtube_upload_select_all_toggles_server_videos_and_deletes_selection() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    script = f"""
{youtube_selection_script_prelude(app_js)}
selectAllYouTubeUploadFiles();
const afterSelectAll = [...state.youtubeUploadSelectedPaths];
const targetAfterSelectAll = youtubeUploadTargetPath();
deleteSelectedYouTubeUploadFiles();
selectAllYouTubeUploadFiles();
console.log(JSON.stringify({{
  afterSelectAll,
  targetAfterSelectAll,
  afterSecondSelectAll: [...state.youtubeUploadSelectedPaths],
  events,
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = json.loads(result.stdout)

    # live/ 녹화 원본은 업로드 목록에 없으므로 전체 선택에도 들어가지 않는다.
    assert output["afterSelectAll"] == [
        "merged/침착맨_라이브_20260826_053736.mp4",
        "split/clip-1.mp4",
    ]
    assert output["targetAfterSelectAll"] is None
    assert output["afterSecondSelectAll"] == []
    assert output["events"] == [
        "render-list",
        "render-ready",
        [
            "delete",
            ["merged/침착맨_라이브_20260826_053736.mp4", "split/clip-1.mp4"],
            "선택한 영상",
        ],
        "render-list",
        "render-ready",
    ]


def test_youtube_upload_file_rows_render_checkbox_and_delete_controls() -> None:
    app_js = read_youtube_upload_javascript()

    assert 'class="selection-control selection-checkbox"' in extract_js_function(
        app_js, "renderYouTubeUploadFileList"
    )
    assert 'type="radio" name="youtube-upload-source"' not in app_js
    assert 'onchange="toggleYouTubeUploadFile(this.value, this.checked)"' in app_js
    assert 'onclick="deleteYouTubeUploadFile(this.dataset.path, event)"' in app_js
    assert 'data-path="${safePathAttribute}"' in app_js
    assert "deleteSourceFiles([path], mergeFileName(path));" in app_js


def test_youtube_upload_ready_blocks_when_more_than_one_file_is_checked() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    target_function = extract_js_function(app_js, "youtubeUploadTargetPath")
    ready_function = extract_js_function(app_js, "renderYouTubeUploadReady")
    script = f"""
const makeElement = (extra = {{}}) => ({{
  classes: new Set(),
  classList: {{
    toggle(name, on) {{ if (on) this.owner.classes.add(name); else this.owner.classes.delete(name); }},
  }},
  ...extra,
}});
const elements = {{}};
for (const id of [
  'btn-youtube-upload', 'youtube-upload-ready', 'youtube-upload-ready-text',
  'youtube-upload-selected-source', 'youtube-upload-step-no',
]) {{
  elements[id] = makeElement({{ disabled: false, textContent: '' }});
  elements[id].classList.owner = elements[id];
}}
elements['youtube-upload-title'] = {{ value: '제목' }};
function $(id) {{ return elements[id] || null; }}
const state = {{
  youtubeOAuthStatus: {{ configured: true, connected: true }},
  youtubeUploadSelectedPaths: new Set(['merged/a.mp4', 'merged/b.mp4']),
}};
{target_function}
{ready_function}
renderYouTubeUploadReady();
const blocked = {{
  disabled: elements['btn-youtube-upload'].disabled,
  reason: elements['youtube-upload-ready-text'].textContent,
  source: elements['youtube-upload-selected-source'].textContent,
  mono: elements['youtube-upload-selected-source'].classes.has('mono'),
}};
state.youtubeUploadSelectedPaths = new Set(['merged/a.mp4']);
renderYouTubeUploadReady();
const ready = {{
  disabled: elements['btn-youtube-upload'].disabled,
  reason: elements['youtube-upload-ready-text'].textContent,
  source: elements['youtube-upload-selected-source'].textContent,
  mono: elements['youtube-upload-selected-source'].classes.has('mono'),
}};
console.log(JSON.stringify({{ blocked, ready }}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert json.loads(result.stdout) == {
        "blocked": {
            "disabled": True,
            "reason": "업로드할 영상은 하나만 남겨 주세요. (2개 선택됨)",
            "source": "2개를 골랐어요. 업로드는 한 번에 하나만 할 수 있어요.",
            "mono": False,
        },
        "ready": {
            "disabled": False,
            "reason": '"제목"을(를) 비공개로 업로드합니다.',
            "source": "merged/a.mp4",
            "mono": True,
        },
    }


def test_youtube_upload_submit_sends_metadata_and_write_marker() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    submit_function = extract_js_function(app_js, "submitYouTubeUpload")
    target_function = extract_js_function(app_js, "youtubeUploadTargetPath")
    script = f"""
const API = '';
const YOUTUBE_MUTATION_HEADERS = Object.freeze({{ 'X-YT-Monitor-Request': '1' }});
const state = {{
  youtubeUploadSelectedPaths: new Set(['merged/final.mp4']),
  youtubeOAuthStatus: {{ configured: true, connected: true }}
}};
{target_function}
const elements = {{
  'youtube-upload-title': {{ value: ' Final title ' }},
  'youtube-upload-description': {{ value: 'Description' }},
  'youtube-upload-tags': {{ value: 'alpha, beta, , gamma' }},
  'youtube-upload-category': {{ value: '22' }},
  'youtube-upload-made-for-kids': {{ checked: true }},
  'btn-youtube-upload': {{ disabled: false, textContent: '비공개로 업로드' }}
}};
const events = [];
function $(id) {{ return elements[id]; }}
async function fetch(url, options) {{
  events.push(['fetch', url, options]);
  return {{ ok: true, json: async () => ({{ id: 'job-12345678' }}) }};
}}
function notify(...args) {{ events.push(['notify', ...args]); }}
function loadYouTubeUploadJobs() {{ events.push(['loadJobs']); }}
function renderYouTubeUploadReady() {{ events.push(['renderReady']); }}
{submit_function}
(async () => {{
  await submitYouTubeUpload({{ preventDefault() {{ events.push(['preventDefault']); }} }});
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

    assert request[0:2] == ["fetch", "/api/youtube/uploads"]
    assert request[2]["method"] == "POST"
    assert request[2]["headers"] == {
        "Content-Type": "application/json",
        "X-YT-Monitor-Request": "1",
    }
    assert json.loads(request[2]["body"]) == {
        "source": "merged/final.mp4",
        "title": "Final title",
        "description": "Description",
        "tags": ["alpha", "beta", "gamma"],
        "category_id": "22",
        "made_for_kids": True,
    }
    assert events[-2:] == [["loadJobs"], ["renderReady"]]


@pytest.mark.parametrize(
    ("outcome", "expected_kind"),
    [
        ("connected", "ok"),
        ("denied", "err"),
        ("invalid_state", "err"),
        ("error", "err"),
    ],
)
def test_youtube_oauth_callback_notifies_and_cleans_query(
    outcome: str,
    expected_kind: str,
) -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    callback_function = extract_js_function(app_js, "handleYouTubeOAuthCallback")
    script = f"""
const events = [];
const state = {{ activeTab: 'merge' }};
const window = {{
  location: {{ href: 'http://localhost/?keep=1&youtube_oauth={outcome}#jobs' }},
  history: {{
    state: {{ marker: 1 }},
    replaceState(stateValue, title, url) {{ events.push(['replaceState', url]); }}
  }}
}};
function notify(title, message, kind) {{ events.push(['notify', title, message, kind]); }}
{callback_function}
const handled = handleYouTubeOAuthCallback();
console.log(JSON.stringify({{ handled, activeTab: state.activeTab, events }}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = json.loads(result.stdout)

    assert output["handled"] is True
    assert output["activeTab"] == "youtube-upload"
    assert output["events"][0][0] == "notify"
    assert output["events"][0][3] == expected_kind
    assert output["events"][1] == ["replaceState", "/?keep=1#jobs"]


def test_unknown_youtube_oauth_query_is_left_untouched() -> None:
    node = require_node()
    app_js = read_youtube_upload_javascript()
    callback_function = extract_js_function(app_js, "handleYouTubeOAuthCallback")
    script = f"""
const events = [];
const state = {{ activeTab: 'merge' }};
const window = {{
  location: {{ href: 'http://localhost/?youtube_oauth=future_value' }},
  history: {{ state: null, replaceState(...args) {{ events.push(args); }} }}
}};
function notify(...args) {{ events.push(args); }}
{callback_function}
console.log(JSON.stringify({{
  handled: handleYouTubeOAuthCallback(), activeTab: state.activeTab, events
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert json.loads(result.stdout) == {
        "handled": False,
        "activeTab": "merge",
        "events": [],
    }


def test_youtube_upload_frontend_javascript_is_valid() -> None:
    node = require_node()
    for filename in YOUTUBE_UPLOAD_JS_FILES:
        result = subprocess.run(
            [node, "--check", str(Path("web", filename))],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        assert result.returncode == 0
        assert result.stderr == ""
