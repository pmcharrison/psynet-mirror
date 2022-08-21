import os
import pathlib

import pytest

from psynet.utils import run_subprocess_with_live_output

psynet_root = pathlib.Path(__file__).parent.parent.resolve()
demo_root = os.path.join(psynet_root, "demos")

print(os.getcwd())


def find_files():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """
    # parent = .parent.joinpath("isolated")
    return sorted(
        [
            # parent.joinpath(file).__str__()
            os.path.join("isolated", file)
            for file in os.listdir("isolated")
            if file.endswith(".py")
        ]
    )


@pytest.mark.parametrize("pytest_script", find_files())
def test_all_isolated(pytest_script):
    run_subprocess_with_live_output(f"pytest -x -s --chrome {pytest_script}")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
