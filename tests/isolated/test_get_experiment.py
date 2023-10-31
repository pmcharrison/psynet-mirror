import pytest

from psynet.pytest_psynet import path_to_demo


def test_old_imports():
    from psynet.timeline import get_trial_maker
    from psynet.utils import get_experiment, import_local_experiment

    with pytest.raises(
        ImportError,
        match="import_local_experiment has moved from psynet.utils to psynet.experiment, please update your import statements.",
    ):
        import_local_experiment()

    with pytest.raises(
        ImportError,
        match="get_experiment has moved from psynet.utils to psynet.experiment, please update your import statements.",
    ):
        get_experiment()

    with pytest.raises(
        ImportError,
        match="get_trial_maker has moved from psynet.timeline to psynet.experiment, please update your import statements.",
    ):
        get_trial_maker("test")


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
@pytest.mark.usefixtures("in_experiment_directory")
def test_get_experiment():
    from psynet.experiment import Experiment, get_experiment

    exp = get_experiment()
    assert isinstance(exp, Experiment)
