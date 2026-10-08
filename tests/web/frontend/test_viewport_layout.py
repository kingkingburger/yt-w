"""브라우저에서 화면 크기별 페이지 접근성과 잘림을 검증한다.

uv run --python 3.13 --with playwright pytest tests/web/frontend/test_viewport_layout.py -q
최초 실행 전: uv run --python 3.13 --with playwright playwright install chromium
"""

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def browser_page():
    files = [
        {"path": f"merged/영상_{i:03}.mp4", "name": f"영상_{i:03}.mp4",
         "size_bytes": 1000000, "mtime": 1700000000}
        for i in range(30)
    ]
    jobs = [
        {"id": f"job-{i:03}", "title": f"업로드 영상 {i}", "source": file["path"],
         "status": "running", "progress_percent": 30, "bytes_uploaded": 300000,
         "total_bytes": 1000000, "elapsed_seconds": 10, "message": "업로드 중"}
        for i, file in enumerate(files)
    ]
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            path = urlparse(route.request.url).path
            if path == "/":
                route.fulfill(path="web/index.html", content_type="text/html; charset=utf-8")
            elif path.startswith("/static/"):
                asset = Path("web", Path(path).name)
                route.fulfill(path=str(asset))
            elif path.startswith("/api/"):
                data = []
                if path == "/api/files":
                    data = files
                elif path == "/api/youtube/uploads":
                    data = jobs
                elif path == "/api/youtube/oauth/status":
                    data = {"configured": True, "connected": True}
                route.fulfill(body=json.dumps(data), content_type="application/json")
            else:
                route.abort()

        page.route("**/*", serve)
        page.goto("http://yt-w.test/")
        page.wait_for_timeout(250)
        yield page, errors
        browser.close()


def assert_fits(page):
    failures = page.evaluate("""() => {
      const selectors = '.sidebar, .content, .viewport-current, .viewport-current .viewport-paged';
      return [...document.querySelectorAll(selectors)].filter(el => el.getClientRects().length)
        .filter(el => el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)
        .map(el => [el.id || el.className, el.clientHeight, el.scrollHeight, el.clientWidth, el.scrollWidth]);
    }""")
    assert failures == []


@pytest.mark.parametrize("size", [(1440, 900), (1280, 720), (1024, 600), (390, 844), (360, 640), (844, 390), (1280, 400), (720, 450)])
def test_all_workspaces_fit_without_scroll(browser_page, size):
    page, errors = browser_page
    page.set_viewport_size({"width": size[0], "height": size[1]})
    for tab in ["youtube-upload", "download", "monitor", "merge", "split", "library"]:
        page.evaluate("tab => switchTab(tab)", tab)
        page.wait_for_timeout(100)
        selector = f"#panel-{tab} .viewport-toolbar select"
        values = page.locator(selector).evaluate("el => [...el.options].filter(o => !o.hidden).map(o => o.value)")
        for value in values:
            page.select_option(selector, value)
            page.wait_for_timeout(80)
            assert_fits(page)
    assert errors == []


@pytest.mark.parametrize("size", [(360, 640), (844, 390)])
def test_download_steps_follow_progress_and_fit(browser_page, size):
    page, errors = browser_page
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.evaluate("switchTab('download')")
    for step in ["analyzing", "result", "downloading", "finished"]:
        page.evaluate("step => showDLStep(step)", step)
        page.wait_for_timeout(100)
        assert page.locator(f"#dl-step-{step}").is_visible()
        assert_fits(page)
    assert errors == []


def test_upload_selection_and_metadata_survive_navigation(browser_page):
    page, errors = browser_page
    page.set_viewport_size({"width": 360, "height": 640})
    page.locator('#youtube-upload-file-list input:visible').first.check()
    page.wait_for_timeout(100)
    selected = page.evaluate("[...state.youtubeUploadSelectedPaths]")
    assert len(selected) == 1
    page.select_option('#panel-youtube-upload .viewport-toolbar select', label='영상 정보')
    page.wait_for_timeout(100)
    page.fill('#youtube-upload-title', '수정한 제목')
    page.select_option('#panel-youtube-upload .viewport-toolbar select', label='서버 영상 고르기')
    page.wait_for_timeout(100)
    assert page.evaluate("[...state.youtubeUploadSelectedPaths]") == selected
    assert page.locator('#youtube-upload-file-list input:checked').count() == 1
    page.select_option('#panel-youtube-upload .viewport-toolbar select', label='영상 정보')
    page.wait_for_timeout(100)
    assert page.locator('#youtube-upload-title').input_value() == '수정한 제목'
    assert_fits(page)
    assert errors == []


@pytest.mark.parametrize("size", [(1280, 720), (360, 640), (844, 390)])
def test_dialogs_and_expanded_folders_fit(browser_page, size):
    page, errors = browser_page
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.evaluate("switchTab('library'); state.librarySearchQuery = '영상'; renderLibrary()")
    page.wait_for_timeout(150)
    assert_fits(page)
    page.evaluate("openAddChannelModal()")
    page.wait_for_timeout(250)
    assert page.locator('.modal').evaluate("el => el.scrollHeight <= el.clientHeight + 2")
    page.evaluate("closeAddChannelModal(); openPalettePicker()")
    page.wait_for_timeout(250)
    for selector in [".palette-dialog", ".palette-body", ".palette-grid"]:
        assert page.locator(selector).evaluate("el => el.scrollHeight <= el.clientHeight + 2")
    seen = set()
    while True:
        seen.update(page.locator('.palette-card:visible').evaluate_all("els => els.map(el => el.dataset.paletteId)"))
        button = page.locator('.palette-grid .viewport-pager button').last
        if not button.is_visible() or button.is_disabled():
            break
        button.click()
        page.wait_for_timeout(40)
    assert len(seen) == page.locator('.palette-card').count()
    assert errors == []


def test_every_upload_job_is_reachable_and_refresh_preserves_page(browser_page):
    page, errors = browser_page
    page.set_viewport_size({"width": 390, "height": 640})
    page.select_option("#panel-youtube-upload .viewport-toolbar select", label="YouTube 업로드 작업")
    page.wait_for_timeout(100)
    seen = set()
    while True:
        seen.update(page.locator("#youtube-upload-jobs .job-id:visible").all_text_contents())
        assert_fits(page)
        button = page.locator("#youtube-upload-jobs .viewport-pager button").last
        if button.is_disabled():
            break
        button.click()
        page.wait_for_timeout(40)
    assert len(seen) == 30
    last_page = page.locator("#youtube-upload-jobs .viewport-pager span").inner_text()
    page.evaluate("renderYouTubeUploadJobs(state.youtubeUploadJobs)")
    page.wait_for_timeout(100)
    assert page.locator("#youtube-upload-jobs .viewport-pager span").inner_text() == last_page
    assert errors == []


@pytest.mark.parametrize("has_upload_file", [False, True])
def test_recordings_are_visible_and_can_open_split_without_becoming_uploads(browser_page, has_upload_file):
    page, errors = browser_page
    recordings = [
        {"path": f"live/channel/recording-{i:02}.mp4", "name": f"recording-{i:02}.mp4",
         "size_bytes": 1000000, "mtime": 1700000000}
        for i in range(18)
    ]
    files = [*recordings]
    if has_upload_file:
        files.append({"path": "merged/final.mp4", "name": "final.mp4", "size_bytes": 1000000})
    page.route("**/api/files*", lambda route: route.fulfill(body=json.dumps(files), content_type="application/json"))
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    page.wait_for_timeout(250)
    assert page.locator('#youtube-upload-file-list .empty').count() == 0
    assert page.locator('#youtube-upload-file-list input:disabled').count() == len(recordings)
    assert page.locator('#youtube-upload-file-list input:not(:disabled)').count() == int(has_upload_file)
    assert page.locator('#btn-youtube-select-all').is_disabled() == (not has_upload_file)
    seen = set()
    while True:
        seen.update(page.locator('#youtube-upload-file-list input:visible').evaluate_all('els => els.map(el => el.value)'))
        assert_fits(page)
        next_button = page.locator('#youtube-upload-file-list .viewport-pager button').last
        if next_button.is_disabled():
            break
        next_button.click()
        page.wait_for_timeout(50)
    assert seen == {file['path'] for file in files}
    page.evaluate("viewportPages.set(document.getElementById('youtube-upload-file-list'), 0); scheduleViewport()")
    page.wait_for_timeout(100)
    page.locator('#youtube-upload-file-list button[data-path]:visible').first.click()
    page.wait_for_timeout(150)
    assert page.evaluate('state.activeTab') == 'split'
    assert page.evaluate('state.splitSelectedPath') == recordings[0]['path']
    assert page.evaluate('[...state.youtubeUploadSelectedPaths]') == []
    assert page.evaluate("document.querySelector('#panel-split .viewport-current').contains(document.getElementById('split-ready'))")
    assert errors == []
