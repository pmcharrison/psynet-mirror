import pytest

from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_get_experiment():
    from psynet.experiment import Experiment, get_experiment

    exp = get_experiment()
    assert isinstance(exp, Experiment)
