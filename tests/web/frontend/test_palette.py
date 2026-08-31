"""영상 기반 color palette picker 계약과 상태 전환 검증."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def require_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is required for the palette frontend tests")
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


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def css_token(block: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}});", block)
    assert match is not None, f"{name} token not found"
    return match.group(1)


def test_palette_picker_exposes_preview_apply_and_reset_controls() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert 'id="palette-trigger"' in html
    assert 'id="palette-overlay"' in html
    assert 'role="dialog" aria-modal="true"' in html
    assert 'id="palette-grid"' in html
    assert 'id="palette-preview-status" role="status" aria-live="polite"' in html
    assert 'onclick="applyPalettePreview()"' in html
    assert 'onclick="cancelPalettePreview()"' in html
    assert 'onclick="resetPalette()"' in html
    assert 'href="https://www.youtube.com/watch?v=23kxFVxYZIY"' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html


def test_palette_catalog_has_sixteen_video_presets() -> None:
    palette_js = Path("web/palette.js").read_text(encoding="utf-8")
    script = f"""
{palette_js}
console.log(JSON.stringify({{
  count: PALETTES.length,
  uniqueIds: new Set(PALETTES.map(palette => palette.id)).size,
  categories: Object.fromEntries(['soft', 'earth', 'vivid'].map(category => [
    category,
    PALETTES.filter(palette => palette.category === category).length,
  ])),
  colorCounts: PALETTES.map(palette => palette.colors.length),
}}));
"""

    result = run_node(script)

    assert result == {
        "count": 16,
        "uniqueIds": 16,
        "categories": {"soft": 5, "earth": 5, "vivid": 6},
        "colorCounts": [2] * 16,
    }


def test_palette_preview_persists_only_after_apply_and_reset_clears_it() -> None:
    palette_js = Path("web/palette.js").read_text(encoding="utf-8")
    script = f"""
const events = [];
const saved = new Map([['yt-w.palette.v1', 'coffee-olive']]);
const storage = {{
  getItem(key) {{ return saved.has(key) ? saved.get(key) : null; }},
  setItem(key, value) {{ saved.set(key, value); }},
  removeItem(key) {{ saved.delete(key); }},
}};
function classList() {{
  const values = new Set();
  return {{
    add(value) {{ values.add(value); }},
    remove(value) {{ values.delete(value); }},
    contains(value) {{ return values.has(value); }},
    toggle(value, on) {{ if (on) values.add(value); else values.delete(value); }},
  }};
}}
const elements = {{
  'palette-trigger-name': {{ textContent: '' }},
  'palette-trigger-swatches': {{ innerHTML: '' }},
  'palette-grid': {{ innerHTML: '' }},
  'palette-preview-status': {{ textContent: '' }},
  'palette-overlay': {{
    classList: classList(),
    querySelector() {{ return {{ focus() {{ events.push(['focus-card']); }} }}; }},
  }},
}};
const window = {{ localStorage: storage }};
const document = {{
  documentElement: {{ dataset: {{}} }},
  body: {{ classList: classList() }},
  activeElement: {{ focus() {{ events.push(['focus-trigger']); }} }},
  addEventListener(type) {{ events.push(['listen', type]); }},
  querySelectorAll() {{ return []; }},
}};
function $(id) {{ return elements[id] || null; }}
const escapeHtml = value => String(value);
const escapeHtmlAttribute = value => String(value);
function notify(title, message, kind) {{ events.push(['notify', title, message, kind]); }}

{palette_js}

initializePalette();
const initialized = {{
  root: document.documentElement.dataset.palette,
  stored: storage.getItem(PALETTE_STORAGE_KEY),
  trigger: elements['palette-trigger-name'].textContent,
}};

openPalettePicker();
const cardCount = (elements['palette-grid'].innerHTML.match(/data-palette-id=/g) || []).length;
previewPalette('orange-teal');
const previewed = {{
  root: document.documentElement.dataset.palette,
  stored: storage.getItem(PALETTE_STORAGE_KEY),
}};
cancelPalettePreview();
const cancelled = {{
  root: document.documentElement.dataset.palette,
  stored: storage.getItem(PALETTE_STORAGE_KEY),
}};

openPalettePicker();
previewPalette('orange-teal');
applyPalettePreview();
const applied = {{
  root: document.documentElement.dataset.palette,
  stored: storage.getItem(PALETTE_STORAGE_KEY),
  trigger: elements['palette-trigger-name'].textContent,
}};

resetPalette();
const reset = {{
  root: document.documentElement.dataset.palette,
  stored: storage.getItem(PALETTE_STORAGE_KEY),
  trigger: elements['palette-trigger-name'].textContent,
}};

console.log(JSON.stringify({{ initialized, cardCount, previewed, cancelled, applied, reset, events }}));
"""

    result = run_node(script)

    assert result["initialized"] == {
        "root": "coffee-olive",
        "stored": "coffee-olive",
        "trigger": "커피 올리브",
    }
    assert result["cardCount"] == 16
    assert result["previewed"] == {
        "root": "orange-teal",
        "stored": "coffee-olive",
    }
    assert result["cancelled"] == {
        "root": "coffee-olive",
        "stored": "coffee-olive",
    }
    assert result["applied"] == {
        "root": "orange-teal",
        "stored": "orange-teal",
        "trigger": "오렌지 틸",
    }
    assert result["reset"] == {
        "root": "studio",
        "stored": None,
        "trigger": "Studio 기본",
    }
    assert [event[1] for event in result["events"] if event[0] == "notify"] == [
        "색 조합 적용",
        "색 조합 초기화",
    ]


def test_every_palette_has_a_semantic_css_token_set() -> None:
    palette_js = Path("web/palette.js").read_text(encoding="utf-8")
    palette_css = Path("web/palette.css").read_text(encoding="utf-8")
    palette_ids = re.findall(r"id: '([a-z0-9-]+)'", palette_js)

    assert len(palette_ids) == 16
    for palette_id in palette_ids:
        selector = f"html[data-palette='{palette_id}']"
        assert selector in palette_css
        block = palette_css[palette_css.index(selector) :]
        block = block[: block.index("}")]
        for token in (
            "--bench:",
            "--action:",
            "--action-rgb:",
            "--acid:",
            "--acid-rgb:",
            "--rack:",
            "--rack-rgb:",
        ):
            assert token in block

    assert "--rec:" not in palette_css
    assert "--ok:" not in palette_css
    assert "--warn:" not in palette_css
    assert "--danger:" not in palette_css


def test_palette_action_and_primary_text_meet_minimum_contrast() -> None:
    palette_js = Path("web/palette.js").read_text(encoding="utf-8")
    palette_css = Path("web/palette.css").read_text(encoding="utf-8")
    palette_ids = re.findall(r"id: '([a-z0-9-]+)'", palette_js)

    for palette_id in palette_ids:
        match = re.search(
            rf"html\[data-palette='{re.escape(palette_id)}'\]\s*\{{(.*?)\n\}}",
            palette_css,
            flags=re.DOTALL,
        )
        assert match is not None
        block = match.group(1)
        action = css_token(block, "--action")
        acid = css_token(block, "--acid")
        acid_ink = css_token(block, "--acid-ink")

        assert contrast_ratio(action, "#FFFFFF") >= 4.5, palette_id
        assert contrast_ratio(acid, acid_ink) >= 4.5, palette_id


def test_palette_boot_runs_before_styles_and_runtime_picker() -> None:
    html = Path("web/index.html").read_text(encoding="utf-8")

    boot_position = html.index('src="/static/palette_boot.js"')
    css_position = html.index('href="/static/app.css"')
    picker_position = html.index('src="/static/palette.js"')
    app_position = html.index('src="/static/app.js"')

    assert boot_position < css_position
    assert picker_position < app_position
    assert "initializePalette();" in Path("web/app.js").read_text(encoding="utf-8")
