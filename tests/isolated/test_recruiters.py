from unittest.mock import MagicMock, patch

from dallinger.prolific import ProlificServiceException

from psynet.recruiters import PsyNetProlificRecruiterMixin


def make_participant():
    participant = MagicMock()
    participant.assignment_id = "submission-1"
    return participant


def test_check_assignment_return_status_returns_true_for_returned_submission():
    participant = make_participant()
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.return_value = {
        "status": "RETURNED"
    }

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        result = PsyNetProlificRecruiterMixin.check_assignment_return_status(
            participant
        )

    assert result is True
    assert participant.var.assignment_returned is True


def test_check_assignment_return_status_handles_prolific_lookup_failure(caplog):
    participant = make_participant()
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.side_effect = (
        ProlificServiceException("Prolific submission was not accessible")
    )

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        result = PsyNetProlificRecruiterMixin.check_assignment_return_status(
            participant
        )

    assert result is False
    assert participant.var.assignment_returned is False
    assert any(
        "Treating the assignment as not returned yet" in record.message
        for record in caplog.records
    )
