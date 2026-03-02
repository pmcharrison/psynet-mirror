from psynet.translation.utils import create_translation_template_with_pybabel


class DummySpinner:
    text = ""


def test_jinja_translation_keywords_are_extracted(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    template_path = templates_dir / "example.html"
    # PsyNet encourages gettext/pgettext and _/_p forms in templates.
    # This test ensures the keyword rules in psynet.translation.utils
    # (_BABEL_JINJA_CONFIG and pybabel -k flags) extract all four.
    template_path.write_text(
        '{{ gettext("Next") }} '
        '{{ pgettext("context", "Hello") }} '
        '{{ _("Continue") }} '
        '{{ _p("button", "Submit") }}',
        encoding="utf-8",
    )

    entries = create_translation_template_with_pybabel(str(tmp_path), DummySpinner())
    msgids = {(entry.msgctxt or None, entry.msgid) for entry in entries}

    assert (None, "Next") in msgids
    assert ("context", "Hello") in msgids
    assert (None, "Continue") in msgids
    assert ("button", "Submit") in msgids
