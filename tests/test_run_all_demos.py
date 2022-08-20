import os
import pathlib

import pytest

from psynet.utils import run_subprocess_with_live_output

psynet_root = pathlib.Path(__file__).parent.parent.resolve()
demo_root = os.path.join(psynet_root, "demos")


def find_demo_dirs():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """
    return sorted(
        [
            dir
            for dir, sub_dirs, files in os.walk(demo_root)
            if "experiment.py" in files and not dir.endswith("/develop")
        ]
    )


demos = find_demo_dirs()

skip = [
    "error_handling",  # Purposefully causes errors
    "singing_iterated",  # Relies on melody package, which needs updating
    "timeline_with_error",  # Purposefully causes an error
]

# start_after = None
start_after = "tapping_static"
index = [i for i, demo in enumerate(demos) if demo.endswith(start_after)][0]
demos = demos[(index + 1) :]


@pytest.mark.parametrize("experiment_directory", demos, indirect=True)
def test_all_demos(in_experiment_directory):
    run_subprocess_with_live_output("pytest -x -s -q test.py")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
# If you see an error and you want to debug an individual experiment,
# navigate to that experiment's test.py and read the setup instructions there.
