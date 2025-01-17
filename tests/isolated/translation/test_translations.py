import pytest

from psynet.translation.check import assert_variable_names_match
from psynet.translation.translate import check_translations


def make_entry(msgid="", msgstr=""):
    """Create a translation entry with source and translated text."""
    return type("Entry", (), {"msgid": msgid, "msgstr": msgstr})


def make_entries(source_text, translated_text):
    """Create matching pot and po entries for testing."""
    key = (source_text, None)
    return (
        {key: make_entry(msgid=source_text)},  # pot entries
        {key: make_entry(msgid=source_text, msgstr=translated_text)},  # po entries
    )


def test_matching_variables():
    """Test that translations with matching variables pass."""
    # Basic variable matching
    pot_entries, po_entries = make_entries("Hello %(name)s", "Bonjour %(name)s")
    assert_variable_names_match(pot_entries, po_entries)

    # Multiple variables
    pot_entries, po_entries = make_entries(
        "%(greeting)s %(name)s", "%(name)s %(greeting)s"
    )
    assert_variable_names_match(pot_entries, po_entries)

    # Jinja style variables
    pot_entries, po_entries = make_entries("Hello {name}", "Bonjour {name}")
    assert_variable_names_match(pot_entries, po_entries)

    # Empty strings
    pot_entries, po_entries = make_entries("", "")
    assert_variable_names_match(pot_entries, po_entries)


def test_mismatched_variables():
    """Test that translations with mismatched variables raise ValueError."""
    # Wrong variable name
    pot_entries, po_entries = make_entries("Hello %(name)s", "Bonjour %(wrong)s")
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries)

    # Missing variable
    pot_entries, po_entries = make_entries("Hello %(name)s", "Bonjour")
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries)

    # Extra variable
    pot_entries, po_entries = make_entries("Hello", "Bonjour %(extra)s")
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries)


def test_multiple_entries():
    """Test checking multiple translations at once."""
    pot_entries = {
        ("Hello %(name)s", None): make_entry("Hello %(name)s"),
        ("Bye %(name)s", None): make_entry("Bye %(name)s"),
    }

    # All correct
    po_entries = {
        ("Hello %(name)s", None): make_entry(
            msgid="Hello %(name)s", msgstr="Hola %(name)s"
        ),
        ("Bye %(name)s", None): make_entry(
            msgid="Bye %(name)s", msgstr="Adios %(name)s"
        ),
    }
    assert_variable_names_match(pot_entries, po_entries)

    # One wrong
    po_entries_one_wrong = {
        ("Hello %(name)s", None): make_entry(
            msgid="Hello %(name)s", msgstr="Hola %(wrong)s"
        ),
        ("Bye %(name)s", None): make_entry(
            msgid="Bye %(name)s", msgstr="Adios %(name)s"
        ),
    }
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries_one_wrong)


@pytest.mark.skip
def test_run():
    VARIABLE_PLACEHOLDERS = {
        "BASE_PAYMENT": 0.1,
        "TIME_REWARD": 0.1,
        "CURRENCY": "$",
        "EMAIL": "dummy@email.com",
        "MIN_ACCUMULATED_REWARD_FOR_ABORT": 2,
        "PERFORMANCE_REWARD": 1.2,
        "TERMINATION_TIME": 120,
        "AGE": 12,
        "HIDE_AFTER": 2,
    }
    check_translations(variable_placeholders=VARIABLE_PLACEHOLDERS)
