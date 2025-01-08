import pytest

from psynet.translation.translators import ChatGptTranslator, GoogleTranslator

TEST_TRANSLATIONS = [
    ("Hello", "Bonjour"),
    ("Goodbye", "Au revoir"),
    ("Thank you", "Merci"),
]


@pytest.mark.parametrize("translator_class", [GoogleTranslator, ChatGptTranslator])
@pytest.mark.parametrize("english,expected_french", TEST_TRANSLATIONS)
def test_translator(translator_class, english, expected_french):
    """
    Test that translators correctly handle basic English to French translations.

    Parameters
    ----------
    translator_class : class
        The translator class to test
    english : str
        Input English text
    expected_french : str
        Expected French translation
    """
    translator = translator_class()
    result = translator.translate(texts=[english], source_lang="en", target_lang="fr")

    assert len(result) == 1
    assert result[0].lower().strip() == expected_french.lower().strip()


def test_invalid_language():
    """Test that translators properly handle invalid language codes."""
    translator = GoogleTranslator()

    # TODO - raise a more specific exception here
    with pytest.raises(Exception):
        translator.translate(
            texts=["Hello"], source_lang="en", target_lang="invalid_code"
        )
