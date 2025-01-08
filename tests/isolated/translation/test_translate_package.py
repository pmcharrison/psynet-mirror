import shutil
import time
from pathlib import Path

import pytest

from psynet.translation.translate_package import translate_package
from psynet.utils import get_psynet_root

mock_translate_counter = -1


def mock_translate_func(texts, source_lang, target_lang, file_path=None):
    global mock_translate_counter
    mock_translate_counter += 1
    return [f"{source_lang} -> {target_lang} {i}" for i in range(len(texts))]


def reset_mock_translate_counter():
    global mock_translate_counter
    mock_translate_counter = -1


@pytest.fixture
def backup_locales():
    """Backup and restore psynet/locales directory during test."""
    locales_dir = Path(get_psynet_root()) / "psynet" / "locales"
    backup_dir = locales_dir.parent / "locales_backup"

    # Backup existing locales if they exist
    if locales_dir.exists():
        shutil.move(locales_dir, backup_dir)

    # Create fresh locales dir
    locales_dir.mkdir(exist_ok=True)

    yield

    # Restore from backup
    if locales_dir.exists():
        shutil.rmtree(locales_dir)
    if backup_dir.exists():
        shutil.move(backup_dir, locales_dir)


def test_translate_psynet(mocker, backup_locales):
    """
    Tests the logic for translating the PsyNet package.

    The autotranslator function is mocked to produce outputs of the following form:
    "source_language: en, target_language: fr, source_text: Hello, target_text: Bonjour, call_id: 1"
    where call_id is a unique identifier for the call to the autotranslator.

    We run this test on the local PsyNet package. To avoid overwriting the pre-existing translations,
    we use a fixture to backup the original contents of "psynet/locales" while running this test.
    """
    mock_translate = mocker.patch(
        "psynet.translation.translators.DefaultTranslator.translate"
    )
    mock_translate.side_effect = mock_translate_func

    reset_mock_translate_counter()
    translate_package(["fr", "de"])

    time.sleep(100000)

    # Verify the mock was called with expected arguments
    # The exact texts will depend on what's in the package, so we don't verify those
    calls = mock_translate.call_args_list
    assert len(calls) > 0

    # Verify each call used correct source/target languages
    languages_called = []
    for call in calls:
        _, kwargs = call
        source_lang = kwargs.get("source_lang")
        target_lang = kwargs.get("target_lang")
        assert source_lang == "en"
        languages_called.append(target_lang)

    # Verify both target languages were used
    assert set(languages_called) == {"fr", "de"}
