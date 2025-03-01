import re
from pathlib import Path

import pytest

import psynet.version
from psynet.utils import list_experiment_dirs

demos = list_experiment_dirs(for_ci_tests=True)


@pytest.mark.parametrize("demo_directory", demos)
def test_check_dallinger_version_in_demo_constraints(demo_directory):
    """
    Checks that the dallinger version in the demo constraints.txt files corresponds to
    psynet.version.dallinger_recommended_version.

    Note
    ----

    We could also implement a similar check for the psynet version, but this would be a bit
    complicated because often the local psynet version will have a development version number
    (e.g. 11.10.0-dev0) and we don't want to insist that constraints.txt also have this.
    """
    constraints_path = Path(demo_directory) / "constraints.txt"
    assert constraints_path.exists()

    dallinger_version = get_dallinger_version(constraints_path)

    assert dallinger_version == psynet.version.dallinger_recommended_version


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
