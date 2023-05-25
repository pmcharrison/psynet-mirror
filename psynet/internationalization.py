import os
import re
import sys
import tempfile
from collections import OrderedDict
from os.path import exists
from os.path import join as join_path

import pandas as pd
import pexpect
import polib

from . import log
from .utils import get_language_dict, logger


###################
# PO utilities
###################
def get_locales_dir(locales_dir):
    """Get the locales directory."""
    if locales_dir is None:
        from .utils import LOCALES_DIR

        locales_dir = LOCALES_DIR
    return locales_dir


def create_psynet_translation_template(locales_dir=None):
    """Extract the psynet pot file."""
    locales_dir = get_locales_dir(locales_dir)
    psynet_folder = locales_dir.replace("psynet/locales", "")
    pot_path = join_path(locales_dir, "psynet.pot")
    n_translatable_strings = create_pot(
        psynet_folder, "psynet/.", pot_path, start_with_fresh_file=True
    )
    print(f"Extracted {n_translatable_strings} translatable strings in {pot_path}")
    return load_po(pot_path)


def new_pot(fpath):
    """Returns an empty pot file."""
    pot = polib.POFile()
    pot.metadata = {
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    pot.encoding = "utf-8"
    pot.metadata_is_fuzzy = ["fuzzy"]
    pot.fpath = fpath
    return pot


def load_po(po_path):
    """Load a pot or po from file."""
    assert po_path.endswith((".po", ".pot")), "po_path must end with .po or .pot"
    assert exists(po_path), f"File {po_path} does not exist"
    return polib.pofile(po_path)


def get_pot_from_command(cmd, tmp_pot_file):
    """Create a pot file from a command and open."""
    timeout = 60
    p = pexpect.spawn(cmd, timeout=timeout)
    while not p.eof():
        line = p.readline().decode("utf-8")
        print(line, end="")
    p.close()
    if p.exitstatus > 0:
        sys.exit(p.exitstatus)
    if os.path.exists(tmp_pot_file):
        pot = load_po(tmp_pot_file)
        os.remove(tmp_pot_file)
        return list(pot)
    else:
        return []


def create_translation_template_with_pybabel(input):
    """Extract translations from a file or multiple files using pybabel."""
    cfg = """
            [jinja2: **.html]
            encoding = utf-8
            """
    with tempfile.TemporaryDirectory() as tempdir:
        tmp_cfg_file = join_path(tempdir, "babel.cfg")
        tmp_pot_file = join_path(tempdir, "babel.pot")
        with open(tmp_cfg_file, "w") as f:
            f.write(cfg)
        return get_pot_from_command(
            f"pybabel extract -F {tmp_cfg_file} -o {tmp_pot_file} {input}", tmp_pot_file
        )


def create_translation_template_with_xgettext(input_file):
    """Extract translations from a file using xgettext."""
    with tempfile.TemporaryDirectory() as tempdir:
        tmp_pot_file = join_path(tempdir, "xgettext.pot")
        return get_pot_from_command(
            f'xgettext -o {tmp_pot_file} {input_file} -L Python --keyword="_p:1c,2"',
            tmp_pot_file,
        )


def clean_po(po, package_name):
    po = clean_code_occurence_paths_in_po(po, package_name)
    po = remove_duplicate_entries_po(po)
    po.sort()
    return po


def create_pot(
    root_dir: str, input_path: str, pot_path: str, start_with_fresh_file=False
):
    """
    Extract translations from a file or multiple files using pybabel or xgettext.
    Parameters
    ----------
    root_dir :
        path pointing to the root directory of the package or experiment folder

    input_path :
        path pointing to the file or directory to extract translations from

    pot_path :
        path pointing to the pot file to write to

    start_with_fresh_file :
        if ``True``, the pot file will be deleted if it exists before extracting translations

    Returns
    -------
    Returns the number of entries
    """

    absolute_root_dir = os.path.abspath(root_dir)
    package_name = absolute_root_dir.split("/")[-1]
    input_path = join_path(absolute_root_dir, input_path)
    assert os.path.isabs(input_path), "Input path must be absolute."
    if start_with_fresh_file and os.path.exists(pot_path):
        os.remove(pot_path)
    old_entries = []
    new_entries = []
    if os.path.exists(pot_path):
        pot = load_po(pot_path)
        old_entries = list(pot)
    else:
        pot = new_pot(pot_path)
    if input_path.endswith("."):
        new_entries.extend(create_translation_template_with_pybabel(input_path))
        for root, dirs, files in os.walk(input_path[:-1]):
            for file in files:
                if file.endswith(".py"):
                    new_entries.extend(
                        create_translation_template_with_xgettext(join_path(root, file))
                    )
    elif input_path.endswith(".html"):
        new_entries.extend(create_translation_template_with_pybabel(input_path))
    elif input_path.endswith(".py"):
        new_entries.extend(create_translation_template_with_xgettext(input_path))
    else:
        raise ValueError("Input file must be a Python or Jinja file.")
    blocked_entries = [(e.msgid, e.msgctxt) for e in old_entries]
    pot_entries = [
        e for e in new_entries if (e.msgid, e.msgctxt) not in blocked_entries
    ]
    if len(pot_entries) > 0:
        pot.extend(pot_entries)
        pot = clean_po(pot, package_name)
        pot.save(pot_path)
    return len(pot_entries)


def clean_code_occurence_paths_in_po(po, package_name):
    """Make the paths in the code occurrences relative to the package and removes line numbers."""
    key = package_name + "/"
    for entry in po:
        occurrences = sorted(set([occurrence for occurrence, _ in entry.occurrences]))
        # Make paths relative to the package
        occurrences = [
            (key).join(occurrence.split(key)[1:]) for occurrence in occurrences
        ]
        # Only store the file name and not the line numbers
        entry.occurrences = [(occurrence, None) for occurrence in occurrences]
    return po


def remove_unused_translations_po(pot_entries, po):
    """Remove translations which don't occur in the pot file."""
    po_entries = po_to_dict(po)
    entries = []
    for key, pot_entry in pot_entries.items():
        po_entry = po_entries[key]
        po_entry.comment = pot_entry.comment
        entries.append(po_entry)
    po.clear()
    po.extend(entries)
    return po


def remove_duplicate_entries_po(po):
    """Remove duplicate entries from a po file."""
    entries_dict = po_to_dict(po)
    po.clear()
    po.extend(list(entries_dict.values()))
    return po


def po_to_dict(po):
    """Convert a po file to a dictionary. Keys are (msgid, msgctxt) tuples. Makes sure there are no duplicates."""
    entries_dict = OrderedDict()
    for entry in po:
        key = (entry.msgid, entry.msgctxt)
        if key in entries_dict:
            old_entry = entries_dict[key]
            assert old_entry.msgid == entry.msgid
            assert old_entry.msgctxt == entry.msgctxt
            assert old_entry.msgstr == entry.msgstr
        else:
            entries_dict[key] = entry
    return entries_dict


def get_po_path(locale, locales_dir, module):
    return join_path(
        get_locales_dir(locales_dir), locale, "LC_MESSAGES", module + ".po"
    )


def compile_mo(po_path):
    """Compile a po file to a mo file and remove fuzzy entries so the translation is recognized properly."""
    po = load_po(po_path)
    mo_path = po_path.replace(".po", ".mo")
    for entry in po:
        entry.flags = (
            []
        )  # Make sure fuzzy entries are excluded, this will lead to the translation not being recognized
    po.save_as_mofile(mo_path)


#######################
# Validate translations
#######################


def variable_name_check(variable_name):
    """Check if a variable name is uppercase and only contains underscores and capital letters."""
    assert all(
        [letter.isupper() or letter == "_" for letter in variable_name]
    ), f'Variable name "{variable_name}" must be uppercase and may only contain of underscore and capital letters.'


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


def get_all_translations(module, locales_dir):
    from .utils import get_available_locales

    locales = get_available_locales(locales_dir)
    translations = {}
    for locale in locales:
        po_path = join_path(locales_dir, locale, "LC_MESSAGES", module + ".po")
        translations[locale] = load_po(po_path)
    return translations


def extract_variable_names(msgid):
    variable_names = []
    for pattern in [JINJA_PATTERN, F_STRING_PATTERN]:
        variable_names.extend(re.findall(pattern, msgid))
    return variable_names


def extract_variable_names_from_entries(pot_entries):
    extracted_variables = []
    for key, pot_entry in pot_entries.items():
        extracted_variables.extend(extract_variable_names(pot_entry.msgid))
    return list(set(extracted_variables))


def assert_all_variables_defined(extracted_variables, variable_placeholders):
    for variable_name in extracted_variables:
        assert (
            variable_name in variable_placeholders
        ), f"Variable {variable_name} is not defined in VARIABLE_PLACEHOLDERS"
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


def check_translation_capitalization_and_punctuation_match(
    original, translation, locale, check_capitalization=None, check_symbols=True
):
    """
    Check if the capitalization and punctuation of the original and translation match.

    Concretely we check, if the first letter of the translation is capitalized (if the original was) and if the
    translation is completely capitalized if the original was completely capitalized. We skip those tests for languages
    which don't use capitalization, see `LANGUAGES_WITHOUT_CAPITALIZATION`.

    We also check if the white space and punctuation match between the original and translation match. We check the
    first and last character of the original and translation.
    """
    if check_capitalization is None:
        check_capitalization = locale not in LANGUAGES_WITHOUT_CAPITALIZATION
    assert len(original) > 0, f"The original ('{original}') must not be empty."
    assert len(translation) > 0, f"Translation ('{translation}') must not be empty."

    # Inconsistent upper/lower case
    if check_capitalization:
        original_capital = original[0].isupper()
        translation_capital = translation[0].isupper()

        if original_capital is not translation_capital:
            logger.warning(
                f"Output string ('{translation}') should start with a capital letter."
            )

        original_all_capital = original.isupper()
        translation_all_capital = translation.isupper()

        if original_all_capital is not translation_all_capital:
            logger.warning(
                f"Translation ('{translation}') should be all capital letters."
            )

    # Inconsistent whitespace or punctuation
    chars = {
        "white space": lambda x: x == " ",
        "line break": lambda x: x in ["\n", "\r"],
        "period": lambda x: x in [".", "。"],
        "exclamation mark": lambda x: x in ["!", "！"],
        "question mark": lambda x: x in ["?", "？"],
        "colon": lambda x: x in [":", "："],
        "semicolon": lambda x: x in [";", "；"],
        "comma": lambda x: x in [",", "，"],
        "dash": lambda x: x in ["-", "—"],
        "parenthesis": lambda x: x in ["(", ")", "（", "）"],
        "bracket": lambda x: x in ["[", "]", "【", "】"],
        "brace": lambda x: x in ["{", "}", "｛", "｝"],
    }
    if check_symbols:
        for char_label, is_symbol in chars.items():
            for position in ["starts", "ends"]:
                idx = 0 if position == "starts" else -1
                original_has_symbol = is_symbol(original[idx])
                translation_has_symbol = is_symbol(translation[idx])

                if original_has_symbol is not translation_has_symbol:
                    info = f"\nOriginal: '{original}'\nTranslation: '{translation}'"
                    if original_has_symbol and not translation_has_symbol:
                        logger.warning(
                            f"The original {position} with a {char_label}, but the translation doesn't. {info}"
                        )
                    elif translation_has_symbol and not original_has_symbol:
                        logger.warning(
                            f"The translation {position} with a {char_label}, but the original doesn't. {info}"
                        )
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


def _check_translations(
    pot_entries, translations, locales_dir, variable_placeholders, module
):
    import gettext

    extracted_variables = extract_variable_names_from_entries(pot_entries)
    assert_all_variables_defined(extracted_variables, variable_placeholders)
    language_dict = get_language_dict("en")

    for locale, po in translations.items():
        language_name = language_dict[locale]
        logger.info(
            log.bold(f"Checking {locale} translation ({language_name}) for errors...")
        )
        po_entries = po_to_dict(po)

        assert_no_missing_translations(po_entries, pot_entries, locale)

        assert_no_duplicate_translations_in_same_context(po_entries, locale)

        po_path = get_po_path(locale, locales_dir, module)
        compile_mo(po_path)
        translator = gettext.translation(module, locales_dir, [locale])

        for key, po_entry in po_entries.items():
            msgid, msgctxt = key
            msgstr = str(po_entry.msgstr)

            assert_translation_contains_same_variables(msgid, msgstr)
            check_translation_capitalization_and_punctuation_match(
                msgid, msgstr, locale
            )
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


def check_translations(
    module="psynet",
    locales_dir=None,
    variable_placeholders=None,
    create_translation_template_function=create_psynet_translation_template,
):
    locales_dir = get_locales_dir(locales_dir)
    pot = create_translation_template_function(locales_dir)
    pot_entries = po_to_dict(pot)
    translations = get_all_translations(module, locales_dir)

    if variable_placeholders is None:
        variable_placeholders = {}
    _check_translations(
        pot_entries=pot_entries,
        translations=translations,
        locales_dir=locales_dir,
        variable_placeholders=variable_placeholders,
        module=module,
    )
