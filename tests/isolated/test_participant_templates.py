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


def test_abort_pages_use_content_surface():
    templates = resources.files("psynet") / "templates"
    for name in ("abort_possible.html", "abort_not_possible.html"):
        source = (templates / name).read_text(encoding="utf-8")
        assert "psynet-surface" in source, f"{name} is missing the content surface"
