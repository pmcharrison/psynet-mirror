import re
from os.path import join as join_path

import pandas as pd
import pytest

from psynet.utils import (
    compile_mo,
    extract_psynet_translation_template,
    get_all_translations,
    get_po_path,
    get_psynet_root,
    get_translator,
    logger,
    po_to_dict,
)

# TODO create mo files on the fly
# TODO run tests on CI
# TODO run tests as predeploy routine


CJK_LANGUAGES = ["zh", "ja", "ko"]


class TestTranslation(object):
    def __init__(self, placeholders):
        self.checks = [
            {
                "name": "Jinja string",
                "pattern": "%\\((.+?)\\)s",
                "assertion": "equals",
                "additional_checks": [self.variable_name_check],
            },
            {
                "name": "f-string",
                "pattern": "{(.+?)}",
                "assertion": "equals",
                "additional_checks": [self.variable_name_check],
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

        self.variable_patterns = [
            check["pattern"]
            for check in self.checks
            if check["name"] in ["Jinja string", "f-string"]
        ]

        self.placeholders = placeholders

    @staticmethod
    def parse_translation(msgid, msgctxt):
        return msgid if msgctxt is None else f"{msgctxt}: {msgid}"

    @staticmethod
    def variable_name_check(variable_name):
        assert all(
            [letter.isupper() or letter == "_" for letter in variable_name]
        ), f'Variable name "{variable_name}" must be uppercase and may only contain of underscore and capital letters.'

    def translation_warnings(
        self,
        original,
        translation,
        locale,
        check_capitalization=None,
        check_symbols=True,
    ):
        if check_capitalization is None:
            check_capitalization = locale not in CJK_LANGUAGES
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

    def verify_translation(self, input, output, assume_same_order=False):
        for check in self.checks:
            found_entries_input = re.findall(check["pattern"], input)
            found_entries_output = re.findall(check["pattern"], output)
            for additional_check in check.get("additional_checks", []):
                for entry in found_entries_input + found_entries_output:
                    additional_check(entry)
            if check["assertion"] == "equals":
                msg = f"Found entries in input and output do not match: {found_entries_input} != {found_entries_output} for pattern {check['pattern']} in input '{input}' and output '{output}'"
                if assume_same_order:
                    assert found_entries_input == found_entries_output, msg
                else:
                    assert set(found_entries_input) == set(found_entries_output), msg
            elif check["assertion"] == "does_not_contain":
                f_strings_in_original = set(re.findall(check["pattern"], input))
                assert f_strings_in_original == set(
                    re.findall(check["pattern"], output)
                )
                assert len(f_strings_in_original) == 0
            else:
                raise ValueError(f"Unknown assertion {check['assertion']}")
        return True

    def test_translation_verification(self):
        # Jinja strings
        self.verify_translation("Hello %(NAME)s", "Hello %(NAME)s")

        with pytest.raises(AssertionError):
            # Lower case variable name
            self.verify_translation("Hello %(name)s", "Hello %(name)s")

        with pytest.raises(AssertionError):
            # Illegal char
            self.verify_translation("Hello %(NAME#)s", "Hello %(NAME#)s")

        with pytest.raises(AssertionError):
            self.verify_translation("Hello %(NAME)s", "Hello %(DF)s")

        # f-strings
        self.verify_translation("Hello {NAME}", "Hello {NAME}")

        # format strings
        with pytest.raises(AssertionError):
            # empty format strings are not allowed
            self.verify_translation("Hello {}", "Hello {}")

        # HTML tags
        html_in, html_out = (
            "<b>hello</b> <span>good bye</span>",
            "<span>good bye</span> <b>hello</b>",
        )
        self.verify_translation(html_in, html_out)
        with pytest.raises(AssertionError):
            self.verify_translation(html_in, html_out, assume_same_order=True)

    def extract_variable_names(self, msgid):
        variable_names = []
        for pattern in self.variable_patterns:
            variable_names.extend(re.findall(pattern, msgid))
        return variable_names

    def test_translations(self, pot_entries):
        translations = get_all_translations()
        for locale, po in translations.items():
            print(f"Checking {locale}...")
            # Check if any translations are missing
            po_entries = po_to_dict(po)
            missing_translations = [
                key for key in pot_entries.keys() if key not in po_entries
            ]
            missing_translations = [
                self.parse_translation(msgid, msgctxt)
                for msgid, msgctxt in missing_translations
            ]
            if len(missing_translations) > 0:
                [
                    print(missing_translation)
                    for missing_translation in missing_translations
                ]
                raise IndexError(f"Missing translations for {locale} (see above)")

            assert (
                pot_entries.keys() == po_entries.keys()
            ), f"Keys in {locale} do not match keys in template.pot"

            # Check if the same translation does not occur multiple times in the same context
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
                duplicate_translations = list(
                    translation_counts.index[translation_counts > 1]
                )
                msg = f"Same translation occured multiple times in context: {context}. {duplicate_translations}"
                assert all(translation_counts == 1), msg

            for key, entry in po_entries.items():
                msgid, msgctxt = key
                msgstr = entry.msgstr

                # Verify placeholders correctness
                self.verify_translation(msgid, msgstr)

                self.translation_warnings(msgid, msgstr, locale)

    def test_translation_runtime_errors(self, pot_entries):
        extracted_variables = []
        for key, pot_entry in pot_entries.items():
            extracted_variables.extend(self.extract_variable_names(pot_entry.msgid))
        extracted_variables = list(set(extracted_variables))
        for variable_name in extracted_variables:
            assert (
                variable_name in self.placeholders
            ), f"Variable {variable_name} is not defined in VARIABLE_PLACEHOLDERS"

        translations = get_all_translations()
        for locale, po in translations.items():
            print(f"Checking {locale} for runtime errors...")
            po_path = get_po_path(locale)
            compile_mo(po_path)
            gettext, pgettext = get_translator(
                locale, localedir=join_path(get_psynet_root(), "psynet", "locales")
            )
            po_entries = po_to_dict(po)
            for key, po_entry in po_entries.items():
                msgid, msgctxt = key
                translation = str(po_entry.msgstr)
                kwargs = {
                    variable_name: self.placeholders[variable_name]
                    for variable_name in self.extract_variable_names(msgid)
                }
                try:
                    if msgctxt == "":
                        gettext(msgid).format(**kwargs)
                    else:
                        pgettext(msgctxt, msgid).format(**kwargs)
                except Exception as e:
                    raise RuntimeError(
                        f"Runtime error in {locale} for {msgid} with translation {translation}"
                    ) from e


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
    }
    pot = extract_psynet_translation_template()
    pot_entries = po_to_dict(pot)
    test = TestTranslation(VARIABLE_PLACEHOLDERS)
    test.test_translation_verification()
    test.test_translations(pot_entries)
    test.test_translation_runtime_errors(pot_entries)
