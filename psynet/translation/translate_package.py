import os
from typing import List

from psynet.translation.translation import (
    check_languages,
    supported_languages,
    translate_pot,
)
from psynet.translation.utils import create_pot
from psynet.utils import get_package_name, get_package_source_directory


def translate_package(languages: List[str]):
    if len(languages) == 0:
        languages = supported_languages

    check_languages(languages)
    pot_path = create_package_translation_template()

    for language in languages:
        translate_pot(pot_path, target_language=language)


def create_package_translation_template():
    """
    Creates a pot file for the package. This pot file provides a template for the translations of the package.

    We assume that the current working directory is the root of the package (i.e. the directory containing setup.py or pyproject.toml).
    We introspect to find the name of the package and the directory containing the source code.
    We then create the pot file in the locales directory of this source code directory.
    """
    package_name = get_package_name()
    source_directory = get_package_source_directory()
    pot_path = os.path.join(source_directory, "locales", package_name + ".pot")
    pot = create_pot(source_directory, pot_path)
    print(f"Created pot file at {pot_path} with {len(pot)} entries")
    return pot_path
