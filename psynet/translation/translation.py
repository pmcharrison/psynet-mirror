import os
import warnings
from functools import cached_property
from typing import Iterable, List, Optional

import polib
import requests
from tqdm import tqdm

from ..utils import require_exp_directory
from . import supported_languages


@require_exp_directory
def translate_experiment(languages: List[str]):
    from psynet.experiment import get_experiment

    if len(languages) == 0:
        exp = get_experiment()
        languages = exp.supported_languages

    check_languages(languages)

    locales_dir = os.path.join(os.getcwd(), "locales")
    pot_path = os.path.join(locales_dir, "experiment.pot")

    pot = create_experiment_translation_template(pot_path)
    pot.save(pot_path)

    for language in languages:
        translate_pot(pot_path, target_language=language)


def create_experiment_translation_template(pot_path):
    return create_pot(os.getcwd(), ".", pot_path, start_with_fresh_file=True)


def translate_psynet(languages: List[str]):
    if len(languages) == 0:
        languages = supported_languages

    check_languages(languages)

    locales_dir = os.path.join(os.getcwd(), "psynet", "locales")
    pot_path = os.path.join(locales_dir, "psynet.pot")

    pot = create_psynet_translation_template()
    pot.save(pot_path)

    for language in languages:
        translate_pot(pot_path, target_language=language)


def translate_pot(
    pot_path, target_language, source_language="en", remove_unused_entries=False
):
    assert os.path.isabs(pot_path), "Input path must be absolute."
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
        remove_unused_entries,
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
    def __init__(self, context: Optional[str] = None):
        self.context = context
        self.entries = []

    def append(self, entry: polib.POEntry):
        self.entries.append(entry)

    @cached_property
    def translator(self):
        return MetaTranslator()

    @classmethod
    def from_po(
        cls, po: Optional[polib.POFile]
    ) -> dict[tuple[str, str], "TranslationUnit"]:
        units = {}

        if po is None:
            return units

        for entry in po:
            has_context = entry.msgctxt is not None

            if has_context:
                key = ("msgctxt", entry.msgctxt)
            else:
                key = ("msgid", entry.msgid)

            try:
                unit = units[key]
            except KeyError:
                units[key] = unit = TranslationUnit(context=entry.msgctxt)

            unit.append(entry)

        return units

    @classmethod
    def inherit(
        cls,
        new: "dict[tuple[str, str], TranslationUnit]",
        old: "dict[tuple[str, str], TranslationUnit]",
    ):
        result = {}

        for key in new.keys():
            if (
                key in old
                and old[key].is_translated
                and old[key].text_to_translate == new[key].text_to_translate
            ):
                result[key] = old[key]
            else:
                result[key] = new[key]

        return result

    @property
    def is_translated(self):
        return all(entry.msgstr for entry in self.entries)

    @property
    def text_to_translate(self):
        return [entry.msgid for entry in self.entries]

    def translate(self, source_lang, target_lang):
        input_texts = self.text_to_translate

        codebooks = [self._get_codebook(text) for text in input_texts]
        input_texts = [
            self._encode(text, codebook)
            for text, codebook in zip(input_texts, codebooks)
        ]

        translated_texts = self.translator.translate(
            texts=input_texts, source_lang=source_lang, target_lang=target_lang
        )

        translated_texts = [
            self._decode(text, codebook)
            for text, codebook in zip(translated_texts, codebooks)
        ]

        for entry, translated_text in zip(self.entries, translated_texts):
            translated_text = self.fix_translation(translated_text)

            entry.msgstr = translated_text
            entry.flags.append(
                "fuzzy"
            )  # Signals that the translation needs to be reviewed

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

    def _encode(self, text: str, codebook: List[tuple[str, str]]) -> str:
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

    def _decode(self, text: str, codebook: List[tuple[str, str]]) -> str:
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

    def fix_translation(self, translation: str) -> str:
        return translation


def translate_po(pot_path, po_path, source_lang, target_lang, remove_unused_entries):
    old_po = polib.pofile(po_path) if os.path.exists(po_path) else None
    new_po = initialize_po(pot_path, po_path, target_lang)

    old_units = TranslationUnit.from_po(old_po)
    new_units = TranslationUnit.from_po(new_po)

    combined_units = TranslationUnit.inherit(new_units, old_units)

    for translation_unit in tqdm(
        combined_units.values(), f"Translating {source_lang} to {target_lang} ..."
    ):
        if not translation_unit.is_translated:
            translation_unit.translate(source_lang, target_lang)

    raise NotImplementedError

    po = _insert_entries(
        po,
        contexts,
        entries_without_context,
        old_contexts,
        old_entries_without_context,
        remove_unused_entries,
    )
    po = clean_po(po)
    po.save(po_path)


def initialize_po(pot_path, po_path, output_lang):
    po = polib.pofile(pot_path)

    if os.path.exists(po_path):
        old_po = polib.pofile(po_path)
        po.metadata = old_po.metadata
    else:
        po.metadata["Language"] = output_lang
        po.metadata["MIME-Version"] = "1.0"
        po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
        po.metadata["Content-Transfer-Encoding"] = "8bit"

    return po


def _insert_entries(
    po,
    contexts,
    entries_without_context,
    old_contexts,
    old_entries_without_context,
    remove_unused_entries,
):
    # We iterate over the po file, and in-place update with the new translations
    # We also work out what old entries have not been included so far, and add those at the end
    # in alphabetical order.
    #

    raise NotImplementedError


class Translator:
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        raise NotImplementedError

    def _get_response(self, url, json_data):
        response = requests.post(url, json=json_data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error: {response.status_code} {response.reason}")


class DeepLTranslator(Translator):
    # TODO - Enable retry logic once we know what kind of exception needs catching
    # @retry(
    #     retry=retry_if_exception_type(NoResultFound),
    #     wait=wait_exponential(multiplier=1, min=3),
    #     stop=stop_after_delay(4)
    # )
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        assert isinstance(texts, list)
        payload = self._make_payload(texts, source_lang, target_lang)
        response = self._get_response("https://api.deepl.com/jsonrpc", payload)
        return self._parse_response(response)

    def _make_payload(self, sentences: List[str], source_lang: str, target_lang: str):
        return {
            "jsonrpc": "2.0",
            "method": "LMT_handle_jobs",
            "params": {
                "tag_handling": "xml",
                "jobs": self._create_jobs(sentences),
                "lang": {
                    "source_lang_computed": source_lang.upper(),
                    "target_lang": target_lang.upper(),
                },
                "priority": 1,
                "commonJobParams": {
                    "mode": "translate",
                    "browserType": 1,
                    "formality": "formal",
                },
            },
        }

    def _create_jobs(self, sentences, num_alternatives=1):
        return [
            {
                "kind": "default",
                "sentences": [
                    {
                        "text": sentence,
                        "id": i,
                        "prefix": "",
                    },
                ],
                "raw_en_context_before": sentences[:i],
                "raw_en_context_after": sentences[i + 1 :],
                "preferred_num_beams": num_alternatives,
            }
            for i, sentence in enumerate(sentences)
        ]

    def _parse_response(self, json_response):
        return [
            translation["beams"][0]["sentences"][0]["text"]
            for translation in json_response["result"]["translations"]
        ]


class MetaTranslator(Translator):
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        from psynet.translation.languages import (
            get_supported_deepl_languages,
            get_supported_gtrans_languages,
        )

        if target_lang in get_supported_deepl_languages():
            DeepLTranslator().translate(texts, target_lang, source_lang)
        elif target_lang in get_supported_gtrans_languages():
            GoogleTranslator().translate(texts, target_lang, source_lang)
        else:
            raise NotImplementedError(
                f"Language {target_lang} is not supported by DeepL and Google Translate. "
                f"DeepL supports {get_supported_deepl_languages()} and Google Translate supports {get_supported_gtrans_languages()}."
            )


class GoogleTranslator(Translator):
    @cached_property
    def _translator(self):
        from googletrans import Translator

        return Translator()

    # TODO - Enable retry logic once we know what kind of exception needs catching
    # @retry(
    #     retry=retry_if_exception_type(NoResultFound),
    #     wait=wait_exponential(multiplier=1, min=3),
    #     stop=stop_after_delay(4)
    # )
    def translate(self, texts: List[str], source_lang: str, target_lang: str):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)

            assert isinstance(texts, list)

            from googletrans import Translator

            translator = Translator()
            response = translator.translate(
                texts, dest=target_lang.lower(), src=source_lang.lower()
            )

            return [translation.text for translation in response]


# TODO - when creating the pot file, ensure that the same context is not
# used in different files
