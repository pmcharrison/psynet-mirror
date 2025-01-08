import os
from copy import copy
from functools import cached_property
from typing import Iterable, List, Optional

import polib

from psynet.translation.translators import DefaultTranslator

from ..utils import (
    get_package_name,
    get_package_source_directory,
    require_exp_directory,
)
from . import supported_languages
from .utils import create_pot, remove_line_numbers, sort_po


@require_exp_directory
def translate_experiment(languages: List[str]):
    if len(languages) == 0:
        from psynet.experiment import get_experiment

        languages = get_experiment().supported_languages

    namespace = "experiment"
    source_directory = os.getcwd()
    locales_directory = os.path.join(os.getcwd(), "locales")

    translate(namespace, source_directory, locales_directory, languages)


def translate_package(languages: List[str]):
    if len(languages) == 0:
        languages = supported_languages

    namespace = get_package_name()
    source_directory = get_package_source_directory()
    locales_directory = os.path.join(source_directory, "locales")

    translate(namespace, source_directory, locales_directory, languages)


def translate(namespace, source_dir, locales_dir, languages):
    check_languages(languages)

    pot_path = os.path.join(locales_dir, namespace + ".pot")
    pot = create_pot(source_dir, pot_path)

    for language in languages:
        translate_pot(pot_path, target_language=language)

    pot = remove_line_numbers(pot)
    pot.save(pot_path)


def translate_pot(
    pot_path,
    target_language,
    source_language="en",
):
    if not os.path.isabs(pot_path):
        pot_path = os.path.abspath(pot_path)
    assert os.path.exists(pot_path), "Input file does not exist."
    assert pot_path.endswith(".pot"), "Input file must be a POT file."

    po_filename = os.path.basename(pot_path).replace(".pot", ".po")
    dir_name = os.path.join(os.path.dirname(pot_path), target_language, "LC_MESSAGES")
    os.makedirs(dir_name, exist_ok=True)
    po_path = os.path.join(dir_name, po_filename)

    translate_po(
        pot_path,
        po_path,
        source_language,
        target_language,
    )


def check_languages(languages: Iterable[str]):
    from .languages import get_known_languages

    assert isinstance(languages, Iterable) and not isinstance(languages, str)

    known_languages = get_known_languages()
    language_codes = [language[0] for language in known_languages]

    for language in languages:
        if language not in language_codes:
            raise ValueError(f"Unknown language: {language}")

    return True


class TranslationUnit:
    def __init__(self, file: str):
        self.file = file
        self.entries = []

    def append(self, entry: polib.POEntry):
        self.entries.append(entry)

    def __len__(self):
        return len(self.entries)

    @cached_property
    def translator(self):
        return DefaultTranslator()

    def sort(self):
        # We can assume that each entry has only a single occurrence, by virtue of the logic in `from_po`.
        # We can also assume that each entry comes from the same file. So, we just need to look at the first
        # element in entry.occurrences, which is a tuple (file, line_number), and take the second element.
        # Note that this line number is by default a string, so we need to convert it to an integer.
        self.entries.sort(key=lambda entry: int(entry.occurrences[0][1]))

    @classmethod
    def from_po(
        cls, po: Optional[polib.POFile]
    ) -> dict[tuple[str, str], "TranslationUnit"]:
        units = {}

        if po is None:
            return units

        # For each text that we find the po file, we look at each occurrence separately.
        # Our aim is to create a TranslationUnit for each file, which contains one entry per occurrence.
        # This involves creating multiple copies of the same entry, with the same msgid, but different occurrences.
        for entry in po:
            occurrences = entry.occurrences  # list of tuples (file, line_number)
            files = [occurrence[0] for occurrence in occurrences]

            for file, occurrence in zip(files, occurrences):
                try:
                    unit = units[file]
                except KeyError:
                    units[file] = unit = TranslationUnit(file=file)

                _entry = copy(entry)
                _entry.occurrences = [occurrence]

                unit.append(_entry)

        return units

    @classmethod
    def inherit(
        cls,
        new: "dict[tuple[str, str], TranslationUnit]",
        old: "dict[tuple[str, str], TranslationUnit]",
        sort: bool,
    ):
        result = {}

        for key in new.keys():
            if (
                key in old
                and old[key].is_translated
                and set(old[key].text_to_translate) == set(new[key].text_to_translate)
            ):
                # The old translation is already translated, so we will inherit it directly.
                # and not retranslate it.
                # We will however update the `occurrences` property to match the new file.
                old_unit = copy(old[key])
                new_unit = copy(new[key])

                for new_entry, old_entry in zip(new_unit.entries, old_unit.entries):
                    old_entry.occurrences = new_entry.occurrences

                result[key] = old_unit
            else:
                result[key] = new[key]

        if sort:
            for unit in result.values():
                # This sorts each TranslationUnit by line number. This will help the autotranslator algorithms.
                unit.sort()

        return result

    @property
    def is_translated(self):
        return all(entry.msgstr for entry in self.entries)

    @property
    def text_to_translate(self):
        return [entry.msgid for entry in self.entries]

    def translate(self, source_lang, target_lang):
        input_texts = self.text_to_translate

        if self.translator.use_codebook:
            codebooks = [self._get_codebook(text) for text in input_texts]
            input_texts = [
                self._encode(text, codebook)
                for text, codebook in zip(input_texts, codebooks)
            ]

        translated_texts = self.translator.translate(
            texts=input_texts,
            source_lang=source_lang,
            target_lang=target_lang,
            file_path=self.file,
        )

        assert len(translated_texts) == len(input_texts) == len(codebooks)

        if self.translator.use_codebook:
            translated_texts = [
                self._decode(text, codebook)
                for text, codebook in zip(translated_texts, codebooks)
            ]

        for entry, translated_text in zip(self.entries, translated_texts):
            translated_text = self.fix_translation(translated_text)

            entry.msgstr = translated_text
            entry.fuzzy = True  # Signals that the translation needs to be reviewed

    @classmethod
    def _get_codebook(cls, text: str) -> List[tuple[str, str]]:
        """Get codebook mapping text patterns to encoded placeholders.

        Parameters
        ----------
        text : str
            Input text to analyze for patterns that need encoding

        Returns
        -------
        list of tuple
            List of (original_text, encoded_placeholder) pairs
        """
        import re

        codebook = []
        counter = 0
        working_text = text

        # Match Jinja variables {{ VAR }}
        jinja_pattern = r"\{\{[^}]+\}\}"
        matches = list(re.finditer(jinja_pattern, working_text))
        for match in matches:
            original = match.group(0)
            encoded = f"■{counter}■"
            codebook.append((original, encoded))
            working_text = working_text.replace(original, encoded)
            counter += 1

        # Match simple variables { VAR }
        var_pattern = r"\{[^}]+\}"
        matches = list(re.finditer(var_pattern, working_text))
        for match in matches:
            original = match.group(0)
            encoded = f"■{counter}■"
            codebook.append((original, encoded))
            working_text = working_text.replace(original, encoded)
            counter += 1

        # Match HTML tags <tag>...</tag>
        html_pattern = r"<[^>]+>.*?</[^>]+>|<[^/>][^>]*>"
        matches = list(re.finditer(html_pattern, working_text))
        for match in matches:
            original = match.group(0)
            encoded = f"■{counter}■"
            codebook.append((original, encoded))
            working_text = working_text.replace(original, encoded)
            counter += 1

        return codebook

    @classmethod
    def _encode(cls, text: str, codebook: List[tuple[str, str]]) -> str:
        """Encode text by replacing patterns with placeholders.

        Parameters
        ----------
        text : str
            Text to encode
        codebook : list of tuple
            List of (original_text, encoded_placeholder) pairs

        Returns
        -------
        str
            Encoded text with patterns replaced by placeholders
        """
        result = text
        for original, encoded in codebook:
            result = result.replace(original, encoded)
        return result

    @classmethod
    def _decode(cls, text: str, codebook: List[tuple[str, str]]) -> str:
        """Decode text by replacing placeholders with original patterns.

        Parameters
        ----------
        text : str
            Text to decode
        codebook : list of tuple
            List of (original_text, encoded_placeholder) pairs

        Returns
        -------
        str
            Decoded text with placeholders replaced by original patterns
        """
        result = text
        for original, encoded in codebook:
            result = result.replace(encoded, original)
        return result

    @classmethod
    def fix_translation(cls, translation: str) -> str:
        return translation


def translate_po(pot_path, po_path, source_lang, target_lang):
    old_po = polib.pofile(po_path) if os.path.exists(po_path) else None
    new_po = initialize_po(pot_path, po_path, target_lang)

    old_units = TranslationUnit.from_po(old_po)
    new_units = TranslationUnit.from_po(new_po)

    combined_units = TranslationUnit.inherit(new_units, old_units, sort=True)

    n_to_translate = sum(
        1 for unit in combined_units.values() if not unit.is_translated
    )
    n_to_skip = len(combined_units) - n_to_translate

    print(
        f"Skipped translating {n_to_skip} files because no new text was found to translate."
    )

    if n_to_translate > 0:
        print(
            f"Translating {n_to_translate} files from {source_lang} to {target_lang}..."
        )

    for i, translation_unit in enumerate(combined_units.values()):
        if not translation_unit.is_translated:
            print(
                f"Translating file {1 + i} of {len(combined_units)} "
                f"({translation_unit.file}, {len(translation_unit)} entries) "
                f"from {source_lang} to {target_lang}..."
            )
            translation_unit.translate(source_lang, target_lang)

    # This function should try and preserve the ordering of the old_po file where possible
    # Strategy: po should be sorted by (a) file path and (b) line number
    # If the same _() call is used in multiple places, then we keep the first one.
    # We won't actually store the line numbers in the saved version, but we use them for sorting before we remove them
    # from the pot file.

    po = update_po(
        new_po,  # We are going to in-place modify the new_po object:
        combined_units,  # we will incorporate the new translations from combined_units;
        old_po,  # we will preserve any manual translations from old_po.
    )

    po = sort_po(po)
    po = remove_line_numbers(po)

    po.save(po_path)


def update_po(
    new_po: polib.POFile,
    combined_units: dict[tuple[str, str], TranslationUnit],
    old_po: Optional[polib.POFile],
):
    # Flatten the combined_units dictionary into a list of entries
    newly_translated_entries = [
        entry for unit in combined_units.values() for entry in unit.entries
    ]

    # Convert this into a dictionary, keyed by (msgctxt, msgid)
    newly_translated_entries = {
        (entry.msgctxt, entry.msgid): entry for entry in newly_translated_entries
    }

    # Convert old_po into an analogous dictionary, keyed by (msgctxt, msgid), only keeping manual translations
    # (i.e. entries that have the 'fuzzy' flag set)
    if old_po is None:
        old_manual_translations = {}
    else:
        old_manual_translations = {
            (entry.msgctxt, entry.msgid): entry for entry in old_po if entry.fuzzy
        }

    # Iterate over the new_po file.
    # If the entry is in old_manual_translations, then use this old translation.
    # Otherwise, use the new translation from combined_units.
    # If neither works, throw an error.
    for i, entry in enumerate(new_po):
        occurrences = entry.occurrences

        key = (entry.msgctxt, entry.msgid)
        if key in old_manual_translations:
            new_po[i] = old_manual_translations[key]
        elif key in newly_translated_entries:
            new_po[i] = newly_translated_entries[key]
        else:
            raise ValueError(
                f"Entry {key} not found in old_manual_translations or newly_translated_entries"
            )

        new_po[i].occurrences = occurrences

    return new_po


def initialize_po(pot_path, po_path, output_lang):
    po = polib.pofile(pot_path)

    # Preserve the metadata from the old po file if it exists
    if os.path.exists(po_path):
        old_po = polib.pofile(po_path)
        po.metadata = old_po.metadata
    else:
        po.metadata["Language"] = output_lang
        po.metadata["MIME-Version"] = "1.0"
        po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
        po.metadata["Content-Transfer-Encoding"] = "8bit"

    return po
