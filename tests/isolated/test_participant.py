import pytest
from dallinger import db

from psynet.bot import Bot
from psynet.pytest_psynet import path_to_test_experiment


def _add_incomplete_trial(
    trial_class,
    launched_experiment,
    node,
    participant,
    *,
    propagate_failure=False,
):
    incomplete = trial_class(
        experiment=launched_experiment,
        node=node,
        participant=participant,
        propagate_failure=propagate_failure,
        is_repeat_trial=False,
    )
    db.session.add(incomplete)
    db.session.commit()
    assert not incomplete.complete
    return incomplete


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestParticipantFailure:
    @pytest.fixture
    def participant(self, launched_experiment):
        return Bot()

    @pytest.fixture
    def trial(self, launched_experiment, trial_class, node, participant):
        trial = trial_class(
            experiment=launched_experiment,
            node=node,
            participant=participant,
            propagate_failure=False,
            is_repeat_trial=False,
        )
        db.session.add(trial)
        db.session.commit()
        return trial

    @pytest.fixture
    def trial_maker(self, experiment_module):
        maker = experiment_module.trial_maker
        original = maker.fail_trials_on_participant_performance_check
        yield maker
        maker.fail_trials_on_participant_performance_check = original

    def test_exit_fails_incomplete_and_preserves_completed(
        self, participant, trial, trial_class, node, launched_experiment
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )

        participant.fail("premature_exit")

        assert participant.failed
        assert participant.pending_redirect == "unsuccessful_end"
        assert not trial.failed
        assert incomplete.failed

    def test_incomplete_trials_fail_without_trial_maker_routines(
        self, participant, trial_class, node, launched_experiment
    ):
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )
        original_routines = launched_experiment.participant_fail_routines
        launched_experiment.participant_fail_routines = []
        try:
            participant.fail("premature_exit")
        finally:
            launched_experiment.participant_fail_routines = original_routines

        assert participant.failed
        assert incomplete.failed

    def test_default_static_policy_fails_completed_and_incomplete(
        self, participant, trial, trial_class, node, launched_experiment, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )

        assert trial_maker.fail_trials_on_participant_performance_check

        participant.fail("performance_check")

        assert participant.failed
        assert trial.failed
        assert incomplete.failed

    def test_performance_check_can_preserve_completed_trials(
        self, participant, trial, trial_class, node, launched_experiment, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )
        trial_maker.fail_trials_on_participant_performance_check = False

        participant.fail("performance_check")

        assert participant.failed
        assert not trial.failed
        assert incomplete.failed

    def test_returned_assignment_fails_incomplete_and_preserves_completed(
        self, launched_experiment, participant, trial, trial_class, node
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )

        launched_experiment.assignment_returned(participant)

        assert participant.failed
        assert "premature_exit" in participant.failure_tags
        assert "assignment_returned" in participant.failure_tags
        assert not trial.failed
        assert incomplete.failed

    def test_arbitrary_failure_fails_incomplete_but_preserves_completed(
        self, participant, trial, trial_class, node, launched_experiment
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )

        participant.fail("simulated_failure")

        assert participant.failed
        assert not trial.failed
        assert incomplete.failed

    def test_already_failed_return_records_cause_without_premature_exit(
        self, launched_experiment, participant, trial, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        trial_maker.fail_trials_on_participant_performance_check = False

        participant.fail("performance_check")
        assert participant.failed
        assert not trial.failed

        launched_experiment.assignment_returned(participant)

        assert "assignment_returned" in participant.failure_tags
        assert "premature_exit" not in participant.failure_tags
        assert not trial.failed

    def test_already_complete_return_is_noop(
        self, launched_experiment, participant, trial, trial_class, node
    ):
        trial.complete = True
        db.session.commit()
        incomplete = _add_incomplete_trial(
            trial_class, launched_experiment, node, participant
        )
        participant.complete = True
        db.session.commit()

        launched_experiment.assignment_returned(participant)

        assert participant.complete
        assert not participant.failed
        assert "assignment_returned" not in participant.failure_tags
        assert "premature_exit" not in participant.failure_tags
        assert not trial.failed
        assert not incomplete.failed
        assert participant.pending_redirect is None
