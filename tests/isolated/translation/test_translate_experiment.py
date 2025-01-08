import os

import polib
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


po_path = os.path.join("locales", "fr", "LC_MESSAGES", "experiment.po")


@pytest.fixture
def cleanup_po_file():
    yield
    if os.path.exists(po_path):
        os.remove(po_path)


@pytest.mark.usefixtures("in_experiment_directory", "cleanup_po_file")
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("translation")], indirect=True
)
def test_translate_experiment(mocker):
    mock_translate = mocker.patch(
        "psynet.translation.translation.MetaTranslator.translate"
    )

    def mock_translate_func(texts, source_lang, target_lang):
        return [f"{source_lang} -> {target_lang} {i}" for i in range(len(texts))]

    mock_translate.side_effect = mock_translate_func

    translate_experiment(["fr"])

    # We expect all texts within experiment.py to be batched into a single call to the translator
    # (because the rule is that all texts within a single file are translated together)
    mock_translate.assert_called_once_with(
        texts=[
            "Hello, welcome to my experiment!",
            # The text is repeated in the source code file, so we repeat it in the translator too,
            # because in theory this repetition is relevant context for the translator.
            "What is your name?",
            "What is your name?",
            "Hello, ■0■!",  # The variable {NAME} gets encoded as ■0■
            "What is your favorite pet?",
            "dog",
            "cat",
            "fish",
            "hamster",
            "bird",
            "snake",
            "Great, I like ■0■ too!",  # The variable {PET} gets encoded as ■0■
        ],
        source_lang="en",
        target_lang="fr",
    )

    # Expect the translation to be written to the PO file
    global po_path
    assert os.path.exists(po_path)
    po = polib.pofile(po_path)

    # Expected message IDs and their corresponding translations
    expected_entries = [
        ("Hello, welcome to my experiment!", "en -> fr 0"),
        # Unlike the translator, the po file will only contain one entry for "What is your name?".
        # This is because all entries with the same msgid are merged into a single entry in the PO file.
        # Only the last translation is kept; en -> fr 1 is therefore omitted from the PO file.
        ("What is your name?", "en -> fr 2"),
        ("Hello, {NAME}!", "en -> fr 3"),
        ("What is your favorite pet?", "en -> fr 4"),
        ("dog", "en -> fr 5"),
        ("cat", "en -> fr 6"),
        ("fish", "en -> fr 7"),
        ("hamster", "en -> fr 8"),
        ("bird", "en -> fr 9"),
        ("snake", "en -> fr 10"),
        ("Great, I like {PET} too!", "en -> fr 11"),
    ]

    # Check each entry matches expected msgid and translation
    for i, (expected_msgid, expected_msgstr) in enumerate(expected_entries):
        assert po[i].msgid == expected_msgid
        assert po[i].msgstr == expected_msgstr
        assert po[i].fuzzy

        # occurrences is a list of tuples, where each tuple contains (filename, line_number)
        # line_number should be None since we clean the PO file to remove line numbers
        occurrences = po[i].occurrences
        assert len(occurrences) == 1

        occurrence = occurrences[0]
        filename, line_number = occurrence

        assert filename == "experiment.py"
        assert line_number == "" or line_number is None
