"""채널 추가 모달의 구조와 시각 계약 검증."""

from pathlib import Path


def test_add_channel_modal_has_clear_accessible_structure() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")
    modal_start = html.index('<div id="add-channel-overlay"')
    modal_end = html.index('<div id="notif"', modal_start)
    modal = html[modal_start:modal_end]

    assert 'role="dialog" aria-modal="true"' in modal
    assert 'aria-labelledby="add-channel-title"' in modal
    assert 'aria-describedby="add-channel-description"' in modal
    assert 'id="add-channel-title">새 채널 추가</h2>' in modal
    assert 'id="add-channel-description"' in modal
    assert 'aria-label="채널 추가 창 닫기"' in modal
    assert '<label class="label" for="channel-name">채널 이름</label>' in modal
    assert '<label class="label" for="channel-url">채널 URL</label>' in modal
    assert "등록과 동시에 채널 감시를 시작합니다." in modal


def test_add_channel_modal_uses_dedicated_visual_states() -> None:
    css = Path("web/app.css").read_text(encoding="utf-8")

    for selector in (
        ".modal::before",
        ".modal-heading",
        ".modal-icon",
        ".modal-close:hover",
        ".modal-fields .input",
        ".modal-note",
        ".modal-foot .btn.primary",
    ):
        assert selector in css

    assert "@media (max-width: 520px)" in css
    assert "max-height: calc(100dvh - 24px);" in css
    assert "overflow-y: auto;" in css
