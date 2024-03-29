import pytest

from psynet.pytest_psynet import path_to_demo


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
def test_get_experiment():
    from psynet.experiment import Experiment, get_experiment

    exp = get_experiment()
    assert isinstance(exp, Experiment)
