import pytest

from psynet.translation.check import assert_variable_names_match
from psynet.translation.translation import check_translations


# This test needs refactoring
def test_translation_verification():
    # Test variable name matching
    pot_entries = {
        ("Hello %(NAME)s", None): type("Entry", (), {"msgid": "Hello %(NAME)s"}),
        ("Hello {NAME}", None): type("Entry", (), {"msgid": "Hello {NAME}"}),
    }

    # Test matching variables
    po_entries = {
        ("Hello %(NAME)s", None): type("Entry", (), {"msgstr": "Hello %(NAME)s"}),
        ("Hello {NAME}", None): type("Entry", (), {"msgstr": "Hello {NAME}"}),
    }
    assert_variable_names_match(pot_entries, po_entries)

    # Test mismatched variables
    po_entries_mismatch = {
        ("Hello %(NAME)s", None): type("Entry", (), {"msgstr": "Hello %(DIFFERENT)s"}),
        ("Hello {NAME}", None): type("Entry", (), {"msgstr": "Hello {DIFFERENT}"}),
    }
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries_mismatch)

    # Test missing variables
    po_entries_missing = {
        ("Hello %(NAME)s", None): type("Entry", (), {"msgstr": "Hello"}),
        ("Hello {NAME}", None): type("Entry", (), {"msgstr": "Hello"}),
    }
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries_missing)

    # Test extra variables
    po_entries_extra = {
        ("Hello %(NAME)s", None): type(
            "Entry", (), {"msgstr": "Hello %(NAME)s %(EXTRA)s"}
        ),
        ("Hello {NAME}", None): type("Entry", (), {"msgstr": "Hello {NAME} {EXTRA}"}),
    }
    with pytest.raises(ValueError):
        assert_variable_names_match(pot_entries, po_entries_extra)


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
