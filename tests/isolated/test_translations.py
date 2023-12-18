import pytest

from psynet.internationalization import (
    assert_translation_contains_same_variables,
    check_translations,
)


def test_translation_verification():
    # Jinja strings
    assert_translation_contains_same_variables("Hello %(NAME)s", "Hello %(NAME)s")

    with pytest.raises(AssertionError):
        # Lower case variable name
        assert_translation_contains_same_variables("Hello %(name)s", "Hello %(name)s")

    with pytest.raises(AssertionError):
        # Illegal char
        assert_translation_contains_same_variables("Hello %(NAME#)s", "Hello %(NAME#)s")

    with pytest.raises(AssertionError):
        assert_translation_contains_same_variables("Hello %(NAME)s", "Hello %(DF)s")

    # f-strings
    assert_translation_contains_same_variables("Hello {NAME}", "Hello {NAME}")

    # format strings
    with pytest.raises(AssertionError):
        # empty format strings are not allowed
        assert_translation_contains_same_variables("Hello {}", "Hello {}")

    # HTML tags
    html_in, html_out = (
        "<b>hello</b> <span>good bye</span>",
        "<span>good bye</span> <b>hello</b>",
    )
    assert_translation_contains_same_variables(html_in, html_out)
    with pytest.raises(AssertionError):
        assert_translation_contains_same_variables(
            html_in, html_out, assume_same_variable_order=True
        )


def test_run():
    VARIABLE_PLACEHOLDERS = {
        "BASE_PAYMENT": 0.1,
        "BONUS": 0.1,
        "CURRENCY": "$",
        "EMAIL": "dummy@email.com",
        "MIN_ACCUMULATED_BONUS_FOR_ABORT": 2,
        "PERFORMANCE_BONUS": 1.2,
        "TERMINATION_TIME": 120,
        "AGE": 12,
        "HIDE_AFTER": 2,
    }
    check_translations(variable_placeholders=VARIABLE_PLACEHOLDERS)
