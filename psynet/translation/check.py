import importlib
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from yaspin import yaspin

from .. import log
from ..log import bold
from ..utils import (
    get_language_dict,
    get_locales_dir_from_path,
    get_package_name,
    get_package_source_directory,
    is_a_package,
    logger,
)
from .utils import compile_mo, create_pot, get_po_path, load_po, po_to_dict

JINJA_PATTERN = "%\\((.+?)\\)s"
F_STRING_PATTERN = "{(.+?)}"

LANGUAGES_WITHOUT_CAPITALIZATION = [
    "zh",  # Chinese
    "ja",  # Japanese
    "ko",  # Korean
    "th",  # Thai
    "he",  # Hebrew
    "ar",  # Arabic
    "ka",  # Georgian
    "fa",  # Persian
    "ha",  # Hausa
    "ps",  # Pashto
    "ug",  # Uyghur
    "ur",  # Urdu
    "as",  # Assamese
    "be",  # Bengali
    "gu",  # Gujarati
    "hi",  # Hindi
    "kn",  # Kannada
    "ml",  # Malayalam
    "mr",  # Marathi
    "pa",  # Punjabi
    "sa",  # Sanskrit
    "te",  # Telugu
    "bo",  # Tibetan
    "km",  # Khmer
    "lo",  # Lao
]


def variable_name_check(variable_name):
    """Check if a variable name is uppercase and only contains underscores and capital letters."""
    assert all(
        [letter.isupper() or letter == "_" for letter in variable_name]
    ), f'Variable name "{variable_name}" must be uppercase and may only contain of underscore and capital letters.'


def get_translations(namespace, locales_dir, locales):
    translations = {}
    for locale in sorted(locales):
        po_path = os.path.join(locales_dir, locale, "LC_MESSAGES", namespace + ".po")
        if not os.path.exists(po_path):
            raise RuntimeError(f"No translation found for {locale}")
        translations[locale] = load_po(po_path)
    return translations


def extract_variable_names(msgid):
    variable_names = []
    for pattern in [JINJA_PATTERN, F_STRING_PATTERN]:
        variable_names.extend(re.findall(pattern, msgid))
    return variable_names


def assert_variable_names_match(pot_entries, po_entries):
    for key, pot_entry in pot_entries.items():
        pot_variables = extract_variable_names(pot_entry.msgid)
        po_entry = po_entries[key]
        po_variables = extract_variable_names(po_entry.msgstr)
        assert sorted(pot_variables) == sorted(po_variables)


def assert_all_variables_defined(extracted_variables, variable_placeholders):
    for variable_name in extracted_variables:
        assert variable_name in variable_placeholders, (
            f"Variable {variable_name} is not defined in VARIABLE_PLACEHOLDERS. "
            f"Specify all expected variables ({extracted_variables}) in Experiment.variable_placeholders = {{}}."
        )
    return True


def assert_no_missing_translations(po_entries, pot_entries, locale):
    """Check that all translations which are defined in the POT file are also present in the po file"""

    def parse_translation(msgid, msgctxt):
        return msgid if msgctxt is None else f"{msgctxt}: {msgid}"

    missing_translations = [key for key in pot_entries.keys() if key not in po_entries]
    missing_translations = [
        parse_translation(msgid, msgctxt) for msgid, msgctxt in missing_translations
    ]
    if len(missing_translations) > 0:
        [
            logger.error(missing_translation)
            for missing_translation in missing_translations
        ]
        raise IndexError(f"Missing translations for {locale} (see above)")

    assert all(
        [key in po_entries for key in pot_entries.keys()]
    ), f"Keys in {locale} do not match keys in the template"


def assert_no_duplicate_translations_in_same_context(po_entries, locale):
    """
    Check if the same translation does not occur multiple times in the same context.

    In machine translation it happens quite often that similar entries are translated identically, e.g. siminalar items
    in a list of languages then to be translated identically, e.g. Malay and Malayam. These cases are hard to eyeball,
    so we disallow an identical translation within the same context for a different input text.
    """
    import pandas as pd

    translation_dict_list = [
        {
            "msgid": key[0],
            "msgctxt": key[1],
            "msgstr": str(entry.msgstr),
        }
        for key, entry in po_entries.items()
    ]

    translation_df = pd.DataFrame(translation_dict_list)
    for context in translation_df["msgctxt"].unique():
        translation_counts = translation_df.query(
            f"msgctxt == '{context}'"
        ).msgstr.value_counts()
        duplicate_translations = list(translation_counts.index[translation_counts > 1])
        language_name = get_language_dict("en")[locale]
        msg = f"Same translation occured multiple times in context: {context} for {locale} {language_name}. {duplicate_translations}"
        assert all(translation_counts == 1), msg


def assert_translation_contains_same_variables(
    original, translation, assume_same_variable_order=False
):
    """
    Assert that the translation contains the same variables as the original.

    We check the following patterns: jinja variables, f-strings, format strings, and HTML tags. Machine translations
    tend to translate variable names, which will lead to runtime errors. Also, quite often HTML tags are not translated
    properly or are not correctly closed.

    To reduce ambiguity in the translation, we assume each variable name is capital letters and underscores only (see
    `variable_name_check`). We therefore do not allow empty variable placeholders (e.g. `{}`) in the original or
    translation.
    """
    variable_checks = [
        {
            "name": "Jinja string",
            "pattern": JINJA_PATTERN,
            "assertion": "equals",
            "additional_checks": [variable_name_check],
        },
        {
            "name": "f-string",
            "pattern": F_STRING_PATTERN,
            "assertion": "equals",
            "additional_checks": [variable_name_check],
        },
        {
            "name": "format string",
            "pattern": "{}",
            "assertion": "does_not_contain",
        },
        {
            "name": "HTML tag",
            "pattern": "<(.+?)>",
            "assertion": "equals",
        },
    ]
    for check in variable_checks:
        found_entries_original = re.findall(check["pattern"], original)
        found_entries_translation = re.findall(check["pattern"], translation)
        for additional_check in check.get("additional_checks", []):
            for entry in found_entries_original + found_entries_translation:
                additional_check(entry)
        if check["assertion"] == "equals":
            msg = f"Found entries in original and translation do not match: {found_entries_original} != {found_entries_translation} for pattern {check['pattern']} in original '{original}' and translation '{translation}'"
            if assume_same_variable_order:
                assert found_entries_original == found_entries_translation, msg
            else:
                assert set(found_entries_original) == set(
                    found_entries_translation
                ), msg
        elif check["assertion"] == "does_not_contain":
            f_strings_in_original = set(re.findall(check["pattern"], original))
            assert f_strings_in_original == set(
                re.findall(check["pattern"], translation)
            )
            assert len(f_strings_in_original) == 0
        else:
            raise ValueError(f"Unknown assertion {check['assertion']}")
    return True


def assert_no_runtime_errors(
    gettext, pgettext, locale, msgid, msgstr, msgctxt, variable_placeholders
):
    """Make sure that the translation does not raise a runtime error when replacing the variable."""
    kwargs = {
        variable_name: variable_placeholders[variable_name]
        for variable_name in extract_variable_names(msgid)
    }
    try:
        if msgctxt == "":
            gettext(msgid).format(**kwargs)
        else:
            pgettext(msgctxt, msgid).format(**kwargs)
    except Exception as e:
        raise RuntimeError(
            f"Runtime error in {locale} for {msgid} with translation {msgstr}"
        ) from e


def _check_translations(pot_entries, translations, locales_dir, namespace):
    import gettext

    language_dict = get_language_dict("en")

    for locale, po in translations.items():
        language_name = language_dict[locale]
        logger.info(
            log.bold(f"Checking {locale} translation ({language_name}) for errors...")
        )
        po_entries = po_to_dict(po)

        assert_variable_names_match(pot_entries, po_entries)

        assert_no_missing_translations(po_entries, pot_entries, locale)

        assert_no_duplicate_translations_in_same_context(po_entries, locale)

        po_path = get_po_path(locale, locales_dir, namespace)
        compile_mo(po_path)
        translator = gettext.translation(namespace, locales_dir, [locale])

        for key, po_entry in po_entries.items():
            msgid, msgctxt = key
            msgstr = str(po_entry.msgstr)

            assert_translation_contains_same_variables(msgid, msgstr)

            variables = extract_variable_names(msgid)
            variable_placeholders = dict(zip(variables, len(variables) * [""]))
            assert_no_runtime_errors(
                translator.gettext,
                translator.pgettext,
                locale,
                msgid,
                msgstr,
                msgctxt,
                variable_placeholders,
            )
        os.remove(po_path.replace(".po", ".mo"))


def check_translations(path=".", locales: Optional[list[str]] = None):
    path = Path(path)
    locales_dir = get_locales_dir_from_path(path)

    if is_a_package(path):
        source_directory = get_package_source_directory(path)
        namespace = get_package_name()
        if locales is None:
            from .languages import supported_locales as psynet_supported_locales

            package = importlib.import_module(namespace)
            locales = getattr(package, "supported_locales", psynet_supported_locales)
    elif (path / "experiment.py").exists():
        from ..experiment import get_experiment

        source_directory = path
        namespace = "experiment"
        if locales is None:
            locales = get_experiment().supported_locales
    else:
        raise ValueError(
            f"{path} does not appear to be either a package or an experiment directory."
        )

    with tempfile.NamedTemporaryFile(suffix=".pot") as f:
        pot_path = f.name
        pot = create_pot(source_directory, pot_path)
        pot_entries = po_to_dict(pot)

    with yaspin() as spinner:
        variable_errors = []
        for key, po_entry in pot_entries.items():
            msgid, msgctxt = key
            msgstr = str(po_entry.msgstr)
            try:
                assert_translation_contains_same_variables(msgid, msgstr)
            except AssertionError as e:
                variable_errors.append(e)
        if len(variable_errors) > 0:
            for error in variable_errors:
                logger.error(error)
            spinner.text = (
                bold("Variable errors found") + " See the details above and fix them."
            )
            spinner.fail("💥")
            exit(1)

    translations = get_translations(namespace, locales_dir, locales)

    _check_translations(
        pot_entries=pot_entries,
        translations=translations,
        locales_dir=locales_dir,
        namespace=namespace,
    )
