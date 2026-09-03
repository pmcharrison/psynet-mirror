"""
Structural guards for the participant-facing templates.

Both invariants here protect against silent rendering failures that are easy to
reintroduce and hard to spot by eye:

* Jinja emits a child template's top-level output *before* the parent's
  ``<!doctype html>``. Anything emitted that way puts the document into quirks
  mode, which changes percentage heights and the box model across every page.
* Overriding ``{% block stylesheets %}`` without calling ``super()`` silently
  drops the participant theme for that page.
"""

import re
from importlib import resources
from pathlib import Path

import pytest

TEMPLATES = sorted(Path(str(resources.files("psynet") / "templates")).rglob("*.html"))

# Dashboard pages are experimenter-facing and inherit a different layout.
PARTICIPANT_TEMPLATES = [p for p in TEMPLATES if not p.name.startswith("dashboard")]

EXTENDS = re.compile(r"\{%-?\s*extends\s")
STYLESHEETS_BLOCK = re.compile(
    r"\{%-?\s*block\s+stylesheets\s*-?%\}(.*?)\{%-?\s*endblock", re.S
)


def _top_level_includes(source):
    """Return includes that sit outside any block, i.e. outside the document."""
    depth = 0
    found = []
    for tag in re.finditer(r"\{%-?\s*(\w+)[^%]*?-?%\}", source):
        keyword = tag.group(1)
        if keyword in {"block", "macro", "if", "for", "call", "filter", "with"}:
            depth += 1
        elif keyword.startswith("end"):
            depth = max(depth - 1, 0)
        elif keyword == "include" and depth == 0:
            found.append(tag.group(0))
    return found


@pytest.mark.parametrize("template", PARTICIPANT_TEMPLATES, ids=lambda p: p.name)
def test_no_output_before_doctype(template):
    source = template.read_text(encoding="utf-8")
    if not EXTENDS.search(source):
        return

    includes = _top_level_includes(source)
    assert not includes, (
        f"{template.name} includes {includes} outside a block. Jinja emits this "
        "before the parent's <!doctype html>, which triggers quirks mode. "
        "Move the include inside a block, or import it as a macro."
    )


@pytest.mark.parametrize("template", PARTICIPANT_TEMPLATES, ids=lambda p: p.name)
def test_stylesheets_block_preserves_theme(template):
    source = template.read_text(encoding="utf-8")
    if not EXTENDS.search(source):
        return

    for block in STYLESHEETS_BLOCK.findall(source):
        if "theme.html" in block:
            # The template supplies the theme itself.
            continue
        assert "super()" in block, (
            f"{template.name} overrides the stylesheets block without calling "
            "super(), which drops participant.css for that page."
        )


def test_focus_ring_follows_accent_token():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    assert "--psynet-focus-ring: 3px solid var(--psynet-accent)" in css


def test_status_colour_tokens_are_defined():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    for token in ("--psynet-danger:", "--psynet-success:", "--psynet-warning:"):
        assert token in css


def test_graphic_vertical_chrome_token_is_defined():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    assert "--psynet-graphic-vertical-chrome:" in css
    assert "--psynet-graphic-min-size:" in css


def test_theme_loads_layout_script():
    source = (resources.files("psynet") / "templates" / "theme.html").read_text(
        encoding="utf-8"
    )
    assert "scripts/psynet.layout.js" in source


def test_psynet_js_attaches_layout_api():
    js = (resources.files("psynet") / "resources/scripts/psynet.js").read_text(
        encoding="utf-8"
    )
    assert "window.psynet = psynet" in js
    assert "psynet.layout = window.psynetLayout" in js


def test_inline_code_follows_the_theme():
    """Bootstrap's default code colour is pink, which reads as an error."""
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index("\ncode {")
    end = css.index("}", start)
    block = css[start:end]
    assert "color: var(--psynet-text)" in block


def test_transient_pages_style_their_spinner():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index(".psynet-activity .spinner-border {")
    end = css.index("}", start)
    block = css[start:end]
    assert "color: var(--psynet-accent)" in block
    assert "width: 2.5rem" in block


def test_media_loading_survives_a_missing_progress_bar():
    """show_footer = false omits the bar, so media loading must not need it."""
    js = (resources.files("psynet") / "resources/scripts/psynet.js").read_text(
        encoding="utf-8"
    )
    for use in re.findall(r"bar\.classList\.(?:add|remove)\([^)]*\)", js):
        index = js.index(use)
        preceding = js[max(0, index - 200) : index]
        assert "if (bar !== null)" in preceding, f"unguarded use: {use}"


def test_footer_reserves_the_progress_bar_strip():
    """The bar is out of flow, so its height has to be reserved explicitly."""
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index("#footer {")
    end = css.index("}", start)
    block = css[start:end]
    assert "var(--psynet-progress-height)" in block


def test_media_bar_mirrors_the_timeline_progress_bar():
    """Same height as the bar at the top of the page, and pinned to the bottom
    of the window when there is no footer to ride."""
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index("#media-download-progress-bar {")
    end = css.index("}", start)
    assert "height: var(--psynet-progress-height)" in css[start:end]

    start = css.index("body:not(:has(#footer)) #media-download-progress-bar {")
    end = css.index("}", start)
    block = css[start:end]
    assert "position: fixed" in block
    assert "bottom: 0" in block
    # An over-constrained fixed box keeps `top`, so it must be released.
    assert "top: auto" in block


def test_footer_clearance_is_scoped_to_pages_with_a_footer():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    assert "body:has(#footer)" in css


def test_vertical_push_buttons_do_not_wrap():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index(".push-button-container--vertical {")
    end = css.index("}", start)
    block = css[start:end]
    assert "flex-wrap: nowrap" in block


def test_push_button_container_grows_with_its_buttons():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index(".push-button-container {")
    end = css.index(".push-button-container--vertical")
    block = css[start:end]
    assert "max-height" not in block
    assert "overflow-y" not in block
    assert "background-color" not in block
    assert "border:" not in block


def test_option_panel_grows_with_its_rows_but_keeps_its_surface():
    """Option rows are white cards, so the panel behind them stays."""
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index(".psynet-options {")
    end = css.index(".psynet-options--horizontal")
    block = css[start:end]
    assert "max-height" not in block
    assert "overflow-y" not in block
    assert "background-color: var(--psynet-surface-sunken)" in block


def test_timeline_omits_footer_when_hidden():
    source = (resources.files("psynet") / "templates" / "timeline-page.html").read_text(
        encoding="utf-8"
    )
    start = source.index("{% macro timeline_footer()")
    end = source.index("{% endmacro %}", start)
    macro = source[start:end]
    assert "{% if config.show_footer != false and footer_has_content %}" in macro
    assert 'id="footer"' in macro
    assert "config.show_footer == false" not in macro
    # An empty footer is omitted, but the media bar still renders.
    assert "{% else %}\n            {{ media_download_bar() }}" in macro


def test_abort_pages_use_content_surface():
    templates = resources.files("psynet") / "templates"
    for name in ("abort_possible.html", "abort_not_possible.html"):
        source = (templates / name).read_text(encoding="utf-8")
        assert "psynet-surface" in source, f"{name} is missing the content surface"


def _audio_meter_macro():
    source = (resources.files("psynet") / "templates/macros/control.html").read_text(
        encoding="utf-8"
    )
    start = source.index("{% macro audio_meter")
    end = source.index("{% macro audio_meter_calibrate")
    return source[start:end]


def test_audio_meter_layout_is_fluid():
    """A 500px table put the coloured status text off the edge of phones."""
    macro = _audio_meter_macro()
    assert "500px" not in macro
    assert "<canvas" not in macro
    assert 'class="audio-meter"' in macro
    assert 'class="audio-meter__track"' in macro
    assert 'class="audio-meter__fill"' in macro
    assert 'id="audio-meter-text"' in macro
    assert 'class="audio-meter__text"' in macro


def test_audio_meter_theme_wraps_inside_the_viewport():
    css = (resources.files("psynet") / "resources/css/participant.css").read_text(
        encoding="utf-8"
    )
    start = css.index(".audio-meter {")
    end = css.index(".audio-meter__track")
    block = css[start:end]
    assert "flex-wrap: wrap" in block
    assert "max-width: 100%" in block
    assert "--psynet-audio-meter-height:" in css
    assert ".audio-meter__fill" in css
