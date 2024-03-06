import os
import pathlib


def find_files():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """
    parent = pathlib.Path(__file__).parent.joinpath("isolated")
    return sorted(
        [
            # parent.joinpath(file).__str__()
            os.path.join(parent, file)
            for file in os.listdir(parent)
            if file.endswith(".py")
        ]
    )


# We no longer use this logic, and instead run the tests via run-ci-tests.sh
#
# @pytest.mark.parametrize("pytest_script", find_files())
# def test_all_isolated(pytest_script):
#     run_subprocess_with_live_output(f"pytest -x -s --chrome {pytest_script}")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
