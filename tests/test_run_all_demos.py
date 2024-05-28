import pytest

from psynet.utils import list_experiment_dirs, working_directory

demos = list_experiment_dirs(for_ci_tests=True)


@pytest.fixture(scope="class")
def _in_experiment_directory(experiment_directory):
    with working_directory(experiment_directory):
        yield experiment_directory


# We no longer use this logic, and instead run the tests via run-ci-tests.sh
#
# @pytest.mark.usefixtures("_in_experiment_directory")
# @pytest.mark.parametrize("experiment_directory", demos, indirect=True)
# def test_all_demos(_in_experiment_directory):
#     run_subprocess_with_live_output("pytest -x -s -q test.py")


# We run the tests in subprocesses to avoid tests contaminating subsequent tests.
# This happens in particular in the context of SQLAlchemy, which can throw strange errors
# once one runs multiple experiments in the same session.
# If you see an error and you want to debug an individual experiment,
# navigate to that experiment's test.py and read the setup instructions there.
