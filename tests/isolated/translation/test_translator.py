import pytest

from psynet.experiment import import_local_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.translation.translators import ChatGptTranslator, GoogleTranslator

TEST_TRANSLATIONS = [
    (["Hello", "Goodbye"], ["Bonjour", "Au revoir"]),
    (["Hello"], ["Bonjour"]),
    (["Goodbye"], ["Au revoir"]),
    (["Thank you"], ["Merci"]),
]


@pytest.mark.usefixtures("in_experiment_directory")
@pytest.mark.parametrize("translator_class", [GoogleTranslator, ChatGptTranslator])
@pytest.mark.parametrize("english,expected_french", TEST_TRANSLATIONS)
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("translation")], indirect=True
)
def test_translator(translator_class, english, expected_french, experiment_directory):
    """
    Test that translators correctly handle basic English to French translations.

    Parameters
    ----------
    translator_class : class
        The translator class to test
    english : list
        Input English texts
    expected_french : list
        Expected French translation
    """
    import_local_experiment()
    translator = translator_class()
    assert len(english) == len(expected_french)
    result = translator.translate(texts=english, source_lang="en", target_lang="fr")

    assert len(english) == len(result)
    assert all(
        [
            translation.lower().strip() == expected_french[i].lower().strip()
            for i, translation in enumerate(result)
        ]
    )


def test_invalid_language():
    """Test that translators properly handle invalid language codes."""
    translator = GoogleTranslator()

    # TODO - raise a more specific exception here
    with pytest.raises(Exception):
        translator.translate(
            texts=["Hello"], source_lang="en", target_lang="invalid_code"
        )
