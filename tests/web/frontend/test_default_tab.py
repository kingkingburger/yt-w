"""Frontend default tab regression tests."""

from pathlib import Path


def test_frontend_opens_youtube_upload_tab_by_default():
    """The site should land directly on the YouTube upload workspace."""
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    assert "activeTab: 'youtube-upload'," in app_js
    assert "switchTab(state.activeTab);" in app_js
    assert "setTimeout(() => $('url-input')?.focus(), 100);" not in app_js

    assert index_html.count('class="nav-btn active"') == 1
    assert '<button class="nav-btn active" data-tab="youtube-upload"' in index_html
    assert '<button class="nav-btn active" data-tab="merge"' not in index_html
    assert '<button class="nav-btn active" data-tab="download"' not in index_html
    assert index_html.index('data-tab="merge"') < index_html.index(
        'data-tab="download"'
    )
    assert index_html.count('class="panel active"') == 1
    assert '<main id="panel-youtube-upload" class="panel active">' in index_html
    assert '<main id="panel-merge" class="panel active">' not in index_html
    assert '<main id="panel-download" class="panel active">' not in index_html
