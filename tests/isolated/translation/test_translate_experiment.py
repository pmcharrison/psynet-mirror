import pytest

from psynet.pytest_psynet import path_to_test_experiment
from psynet.translation.translation import check_languages, translate_experiment


def test_check_languages():
    assert check_languages(["fr", "de"])

    with pytest.raises(ValueError, match="Unknown language: asdas"):
        check_languages(["asdas"])


def test_get_codebook():
    from psynet.translation.translation import TranslationUnit

    entry_collection = TranslationUnit()

    # Test Jinja variables
    text = "Hello {{ NAME }}"
    codebook = entry_collection._get_codebook(text)
    assert codebook == [("{{ NAME }}", "■0■")]

    # Test simple variables
    text = "Hello {NAME}"
    codebook = entry_collection._get_codebook(text)
    assert codebook == [("{NAME}", "■0■")]

    # Test HTML tags
    text = "Hello <b>world</b>"
    codebook = entry_collection._get_codebook(text)
    assert codebook == [("<b>world</b>", "■0■")]

    # Test multiple variables
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = entry_collection._get_codebook(text)
    assert codebook == [
        ("{{ NAME }}", "■0■"),
        ("{AGE}", "■1■"),
        ("<b>world</b>", "■2■"),
    ]


def test_encode_decode():
    from psynet.translation.translation import TranslationUnit

    entry_collection = TranslationUnit()

    # Test encoding
    text = "Hello {{ NAME }} {AGE} <b>world</b>"
    codebook = entry_collection._get_codebook(text)
    encoded = entry_collection._encode(text, codebook)
    assert encoded == "Hello ■0■ ■1■ ■2■"

    # Test decoding
    decoded = entry_collection._decode(encoded, codebook)
    assert decoded == text

    # Test with empty text
    assert entry_collection._encode("", []) == ""
    assert entry_collection._decode("", []) == ""

    # Test with empty codebook
    assert entry_collection._encode("hello", []) == "hello"
    assert entry_collection._decode("hello", []) == "hello"


@pytest.mark.usefixtures("in_experiment_directory")
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("translation")], indirect=True
)
def test_translate_experiment(mocker):
    mock_translate = mocker.patch(
        "psynet.translation.translation.MetaTranslator.translate"
    )

    translate_experiment(["fr"])

    expected_calls = [
        mocker.call(texts=[text], source_lang="en", target_lang="fr")
        for text in [
            "Hello, welcome to my experiment!",
            "What is your name?",
            "Hello, {NAME}!",
            "What is your favorite pet?",
            "dog",
            "cat",
            "fish",
            "hamster",
            "bird",
            "snake",
            "Great, I like {PET} too!",
        ]
    ]
    assert mock_translate.call_args_list == expected_calls
