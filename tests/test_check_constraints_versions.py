import re
from pathlib import Path

import pytest

import psynet.version
from psynet.utils import list_experiment_dirs

demos = list_experiment_dirs(for_ci_tests=True)


def versions_match_at_provided_levels(version1, version2):
    """
    Compare two version strings, matching only the provided levels.

    For example, '12.0' and '12.0.0' will match because we only compare
    the first two parts (major.minor) that are provided in '12.0'.

    Parameters
    ----------
    version1 : str
        First version string to compare
    version2 : str
        Second version string to compare

    Returns
    -------
    bool
        True if versions match at the provided levels, False otherwise
    """
    parts1 = version1.split(".")
    parts2 = version2.split(".")

    # Compare only up to the minimum number of parts provided
    min_parts = min(len(parts1), len(parts2))

    return parts1[:min_parts] == parts2[:min_parts]


@pytest.mark.parametrize("demo_directory", demos)
def test_check_dallinger_version_in_demo_constraints(demo_directory):
    """
    Checks that the dallinger version in the demo constraints.txt files corresponds to
    psynet.version.dallinger_recommended_version.

    Note
    ----

    We could also implement a similar check for the psynet version, but this would be a bit
    complicated because often the local psynet version will have a development version number
    (e.g. 11.10.0a0) and we don't want to insist that constraints.txt also have this.
    """
    constraints_path = Path(demo_directory) / "constraints.txt"
    assert constraints_path.exists()

    dallinger_version = get_dallinger_version(constraints_path)

    assert versions_match_at_provided_levels(
        dallinger_version, psynet.version.dallinger_recommended_version
    )


def get_dallinger_version(constraints_path):
    dallinger_pattern = r"^dallinger(?:\[[^\]]*\])?==([^\s]+)"
    with open(constraints_path) as f:
        constraints_content = f.read()
        for line in constraints_content.splitlines():
            if match := re.match(dallinger_pattern, line):
                dallinger_version = match.group(1)
                break
        else:
            raise AssertionError(
                f"Could not find dallinger version in {constraints_path}"
            )

    return dallinger_version
