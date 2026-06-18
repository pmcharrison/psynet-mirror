from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from dallinger.prolific import ProlificServiceException

from psynet.recruiters import ProlificRecruiter, PsyNetProlificRecruiterMixin


def make_participant(status="screened_out"):
    participant = MagicMock()
    participant.assignment_id = "submission-1"
    participant.status = status
    return participant


def test_check_assignment_return_status_records_returned_participant_status():
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
    assert participant.status == "returned"


def test_check_assignment_return_status_preserves_non_returned_participant_status():
    participant = make_participant(status="screened_out")
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.return_value = {
        "status": "ACTIVE"
    }

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        result = PsyNetProlificRecruiterMixin.check_assignment_return_status(
            participant
        )

    assert result is False
    assert participant.var.assignment_returned is False
    assert participant.status == "screened_out"


def prolific_error(status):
    return ProlificServiceException(
        f'{{"response": {{"error": {{"status": {status}}}}}}}'
    )


@pytest.mark.parametrize("status", [404, 408, 429, 500, 502, 503, 504])
def test_check_assignment_return_status_handles_retriable_prolific_lookup_failure(
    status,
    caplog,
):
    participant = make_participant()
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.side_effect = (
        prolific_error(status)
    )

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        result = PsyNetProlificRecruiterMixin.check_assignment_return_status(
            participant
        )

    assert result is False
    assert participant.var.assignment_returned is False
    assert participant.status == "screened_out"
    assert any(
        "Treating the assignment as not returned yet" in record.message
        for record in caplog.records
    )


def test_check_assignment_return_status_raises_for_non_retriable_prolific_failure():
    participant = make_participant()
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.side_effect = (
        prolific_error(400)
    )

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        with pytest.raises(ProlificServiceException):
            PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)


def test_prolific_run_checks_combines_unread_message_notifications():
    recruiter = object.__new__(ProlificRecruiter)
    recruiter.prolificservice = MagicMock()
    recruiter.prolificservice.get_unread_messages.return_value = [
        {
            "data": {"study_id": "study-1"},
            "sender_id": "worker-1",
            "body": "Hello",
            "sent_at": "2026-06-14T18:00:00Z",
        }
    ]
    notifier = MagicMock()
    notifier.bold.side_effect = lambda text: f"**{text}**"
    notifier.combine.side_effect = lambda *args: "\n".join(args)
    experiment = MagicMock(notifier=notifier)

    with patch.object(
        ProlificRecruiter,
        "current_study_id",
        new_callable=PropertyMock,
        return_value="study-1",
    ):
        with patch("psynet.redis.redis_vars.get", return_value=None):
            with patch("psynet.redis.redis_vars.set") as mark_seen:
                with patch("psynet.experiment.get_experiment", return_value=experiment):
                    recruiter.run_checks()

    mark_seen.assert_called_once()
    notifier.combine.assert_called_once()
    assert notifier.combine.call_args.args[0] == "Found 1 unread messages"
    assert "worker-1" in notifier.combine.call_args.args[1]
    notifier.notify.assert_called_once()
    assert "worker-1" in notifier.notify.call_args.args[0]


def test_prolific_run_checks_handles_current_unread_message_shape():
    recruiter = object.__new__(ProlificRecruiter)
    recruiter.prolificservice = MagicMock()
    recruiter.prolificservice.get_unread_messages.return_value = [
        {
            "id": "message-1",
            "sender": "worker-1",
            "body": "Hello",
            "datetime_created": "2026-06-14T18:00:00Z",
            "data": {
                "study_id": "study-1",
                "category": "technical-issues",
            },
        }
    ]
    notifier = MagicMock()
    notifier.bold.side_effect = lambda text: f"**{text}**"
    notifier.combine.side_effect = lambda *args: "\n".join(args)
    experiment = MagicMock(notifier=notifier)

    with patch.object(
        ProlificRecruiter,
        "current_study_id",
        new_callable=PropertyMock,
        return_value="study-1",
    ):
        with patch("psynet.redis.redis_vars.get", return_value=None):
            with patch("psynet.redis.redis_vars.set") as mark_seen:
                with patch("psynet.experiment.get_experiment", return_value=experiment):
                    recruiter.run_checks()

    mark_seen.assert_called_once()
    notifier.combine.assert_called_once()
    assert "worker-1" in notifier.combine.call_args.args[1]
    assert "2026-06-14T18:00:00Z" in notifier.combine.call_args.args[1]
    notifier.notify.assert_called_once()
