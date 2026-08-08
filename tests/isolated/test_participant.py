import pytest
from dallinger import db

from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestPrematureExitPreservesCompleted:
    def test_premature_exit_respects_trial_maker_opt_out(
        self, participant, trial, trial_maker
    ):
        trial.complete = True
        db.session.commit()

        assert trial_maker.fail_trials_on_premature_exit
        trial_maker.fail_trials_on_premature_exit = False

        participant.fail("premature_exit")

        assert participant.failed
        assert not trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestPrematureExitFailsIncomplete:
    def test_premature_exit_fails_incomplete_even_when_opted_out(
        self, participant, trial, trial_maker
    ):
        assert not trial.complete
        trial_maker.fail_trials_on_premature_exit = False

        participant.fail("premature_exit")

        assert participant.failed
        assert trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestParticipantPerformanceFailure:
    def test_default_static_policy_fails_trials(self, participant, trial, trial_maker):
        trial.complete = True
        db.session.commit()

        assert trial_maker.fail_trials_on_participant_performance_check

        participant.fail("performance_check")

        assert participant.failed
        assert trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestPerformanceCheckFailsIncomplete:
    def test_performance_check_fails_incomplete_even_when_opted_out(
        self, participant, trial, trial_maker
    ):
        assert not trial.complete
        trial_maker.fail_trials_on_participant_performance_check = False

        participant.fail("performance_check")

        assert participant.failed
        assert trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestRecruiterReturnFailure:
    def test_returned_assignment_routes_through_trial_maker_policy(
        self, launched_experiment, participant, trial, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        trial_maker.fail_trials_on_premature_exit = True

        launched_experiment.assignment_returned(participant)

        assert participant.failed
        assert "premature_exit" in participant.failure_tags
        assert "assignment_returned" in participant.failure_tags
        assert trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestRecruiterReturnOptOut:
    def test_returned_assignment_preserves_completed_when_opted_out(
        self, launched_experiment, participant, trial, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        trial_maker.fail_trials_on_premature_exit = False

        launched_experiment.assignment_returned(participant)

        assert participant.failed
        assert "premature_exit" in participant.failure_tags
        assert not trial.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestSettlementReturn:
    def test_already_failed_return_records_cause_without_premature_exit(
        self, launched_experiment, participant, trial, trial_maker
    ):
        trial.complete = True
        db.session.commit()
        trial_maker.fail_trials_on_premature_exit = False
        trial_maker.fail_trials_on_participant_performance_check = False

        participant.fail("performance_check")
        assert participant.failed
        assert not trial.failed

        launched_experiment.assignment_returned(participant)

        assert "assignment_returned" in participant.failure_tags
        assert "premature_exit" not in participant.failure_tags
        assert not trial.failed
