from psynet.translation.utils import create_translation_template_with_pybabel


class DummySpinner:
    text = ""


def test_jinja_gettext_is_extracted(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    template_path = templates_dir / "example.html"
    # Regression guard: Babel 2.18.0 stops extracting gettext(...) from Jinja,
    # while 2.17.0 still extracts both gettext(...) and pgettext(...).
    # Revisit this test if a future Babel release restores extraction.
    template_path.write_text(
        '{{ gettext("Next") }} {{ pgettext("context", "Hello") }}',
        encoding="utf-8",
    )

    entries = create_translation_template_with_pybabel(str(tmp_path), DummySpinner())
    msgids = {(entry.msgctxt or None, entry.msgid) for entry in entries}

    assert (None, "Next") in msgids
    assert ("context", "Hello") in msgids
