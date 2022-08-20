import pytest


def test_old_imports():
    from psynet.experiment import get_experiment, import_local_experiment
    from psynet.timeline import get_trial_maker

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


@pytest.mark.parametrize("experiment_directory", ["../demos/mcmpc"], indirect=True)
def test_get_experiment():
    from psynet.experiment import Experiment, get_experiment

    exp = get_experiment
    assert isinstance(exp, Experiment)
