"""
Test that PsyNet package translations are up-to-date with source code.

This test extracts all translatable strings from the PsyNet source code
and verifies that all existing translation files (PO files) contain
translations for all those strings. It does NOT call any translation API,
making it fast and free to run in CI.

This test only runs on release branches (CI_COMMIT_REF_NAME starts with "release-").
On non-release branches, missing translations are automatically filled in using
the null translator (see run-ci-tests.sh).

If this test fails, it means:
1. New translatable strings were added to PsyNet but not translated, or
2. Existing translations have mismatched variables, or
3. There are other translation quality issues

To fix: run `psynet translate` to update translations.
"""

import os

import pytest

from psynet.translation.check import check_translations
from psynet.utils import get_psynet_root, working_directory


def is_release_branch():
    """Check if we're running on a release branch in CI."""
    branch_name = os.environ.get("CI_COMMIT_REF_NAME", "")
    return branch_name.startswith("release-")


@pytest.mark.skipif(
    not is_release_branch(),
    reason="Translation up-to-date check only runs on release branches",
)
def test_psynet_translations_up_to_date():
    """
    Verify all PsyNet package translations are up-to-date with source code.

    This test:
    1. Extracts all translatable strings from PsyNet source (creates fresh POT)
    2. Compares against existing PO translation files
    3. Fails if any translations are missing or have variable mismatches

    This does NOT call the translation API - it only checks that existing
    translations are complete and valid.

    Only runs on release branches (where CI_COMMIT_REF_NAME starts with "release-").
    """
    with working_directory(get_psynet_root()):
        check_translations(path=".", recreate_pot=True)
