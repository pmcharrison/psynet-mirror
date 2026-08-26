import pytest

from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker


class DummyTrial(StaticTrial):
    time_estimate = 1

    def show_trial(self, experiment, participant):
        pass


def _static_trial_maker(**kwargs):
    defaults = dict(
        id_="dummy",
        trial_class=DummyTrial,
        nodes=[StaticNode(definition={"x": 1})],
        expected_trials_per_participant=1,
        target_n_participants=1,
        recruit_mode="n_participants",
    )
    defaults.update(kwargs)
    return StaticTrialMaker(**defaults)


def test_default_n_participants_completion_is_experiment():
    trial_maker = _static_trial_maker()
    assert trial_maker.n_participants_completion == "experiment"


def test_rejects_unknown_n_participants_completion():
    with pytest.raises(ValueError, match="n_participants_completion"):
        _static_trial_maker(n_participants_completion="session")
