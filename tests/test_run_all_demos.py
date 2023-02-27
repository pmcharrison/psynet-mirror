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

# Skip the recruiter demos because they're not meaningful to run here
demos = [d for d in demos if "demos/recruiters" not in d]

# Skip the video_gibbs demo because it relies on ffmpeg which is not installed in the CI environment
demos = [d for d in demos if "demos/video_gibbs" not in d]

# Uncomment this code if you want to start the test sequence at a particular point
#
# start_after = "video"
# index = [i for i, demo in enumerate(demos) if demo.endswith(start_after)][0]
# demos = demos[(index + 1) :]


@pytest.mark.parametrize("experiment_directory", demos, indirect=True)
def test_all_demos(in_experiment_directory):
    run_subprocess_with_live_output("pytest -x -s -q test.py")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
# If you see an error and you want to debug an individual experiment,
# navigate to that experiment's test.py and read the setup instructions there.
