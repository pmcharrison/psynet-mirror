import pytest

from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestParticipantFailure:
    def test_premature_exit_respects_trial_maker_opt_out(
        self, participant, trial, trial_maker
    ):
        trial_maker.fail_trials_on_premature_exit = False

        participant.fail("premature_exit")

        assert participant.failed
        assert not trial.failed
