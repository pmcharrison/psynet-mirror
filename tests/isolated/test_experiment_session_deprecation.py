import pytest

from psynet.experiment import get_experiment
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_experiment_session_deprecation():
    exp = get_experiment()

    # Once Dallinger v13 is released we should update this test, because it'll probably
    # throw an AttributeError instead of a DeprecationWarning.
    with pytest.warns(DeprecationWarning):
        exp.session
