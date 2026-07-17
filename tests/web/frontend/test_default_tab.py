"""Frontend default tab regression tests."""

from pathlib import Path


def test_frontend_opens_merge_tab_by_default():
    """The site should land directly on the merge workspace."""
    app_js = Path("web/app.js").read_text(encoding="utf-8")
    index_html = Path("web/index.html").read_text(encoding="utf-8")

    assert "activeTab: 'merge'," in app_js
    assert "switchTab(state.activeTab);" in app_js
    assert "setTimeout(() => $('url-input')?.focus(), 100);" not in app_js

    assert '<button class="nav-btn active" data-tab="merge"' in index_html
    assert '<button class="nav-btn active" data-tab="download"' not in index_html
    assert index_html.index('data-tab="merge"') < index_html.index(
        'data-tab="download"'
    )
    assert '<main id="panel-merge" class="panel active">' in index_html
    assert '<main id="panel-download" class="panel active">' not in index_html
