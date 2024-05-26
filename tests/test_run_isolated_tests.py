import pathlib


def find_files():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """
    parent = pathlib.Path(__file__).parent / "isolated"
    parent_demos = parent / "demos"
    parent_experiments = parent / "experiments"
    parent_features = parent / "features"

    python_files = []
    for directory in [parent, parent_demos, parent_experiments, parent_features]:
        python_files.extend(directory.glob("*.py"))

    return sorted(map(str, python_files))


# We no longer use this logic, and instead run the tests via run-ci-tests.sh
#
# @pytest.mark.parametrize("pytest_script", find_files())
# def test_all_isolated(pytest_script):
#     run_subprocess_with_live_output(f"pytest -x -s --chrome {pytest_script}")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
