from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from dallinger.prolific import ProlificServiceException

from psynet.recruiters import (
    BaseLabRecruiter,
    ProlificRecruiter,
    PsyNetProlificRecruiterMixin,
)


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


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
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


def test_check_assignment_return_status_raises_for_missing_prolific_submission(
    caplog,
):
    participant = make_participant()
    experiment = MagicMock()
    experiment.recruiter.prolificservice.get_participant_submission.side_effect = (
        prolific_error(404)
    )

    with patch("psynet.experiment.get_experiment", return_value=experiment):
        with pytest.raises(ProlificServiceException):
            PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)

    assert any(
        "non-retriable lookup error with status 404" in record.message
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


def make_lab_recruiter(token="abc123", base_payment=1.5):
    recruiter = BaseLabRecruiter.__new__(BaseLabRecruiter)
    recruiter.config = {
        "lab_recruiter_auth_token": token,
        "base_payment": base_payment,
    }
    recruiter.external_submission_url = "https://recruiter.example.edu/tasks"
    return recruiter


def make_lab_participant(failed=False):
    participant = MagicMock()
    participant.assignment_id = "assignment-1"
    participant.failed = failed
    participant.failure_tags = ["too_slow"] if failed else []
    participant.bonus = None
    return participant


@pytest.mark.parametrize(
    "failed, url_suffix, failed_reason",
    [
        (False, "/complete", []),
        (True, "/fail", ["too_slow"]),
    ],
)
def test_lab_recruiter_reward_bonus_posts_outcome(failed, url_suffix, failed_reason):
    recruiter = make_lab_recruiter(token="secret-key")
    participant = make_lab_participant(failed=failed)

    with patch("psynet.recruiters.requests.post") as post:
        posted = recruiter.reward_bonus(participant, amount=0.25, reason="completed")

    args, kwargs = post.call_args
    assert args[0] == f"https://recruiter.example.edu/tasks{url_suffix}"
    assert kwargs["headers"] == {"Authorization": "Token secret-key"}
    assert kwargs["json"] == {
        "assignmentId": "assignment-1",
        "basePayment": 1.5,
        "bonus": 0.25,
        "failed_reason": failed_reason,
    }
    assert kwargs.get("verify", True) is True
    assert kwargs["timeout"] == BaseLabRecruiter.post_timeout_seconds
    assert posted is True


def test_lab_recruiter_reward_bonus_skips_post_when_token_missing(caplog):
    recruiter = make_lab_recruiter(token="")
    participant = make_lab_participant()

    with (
        patch("psynet.recruiters.requests.post") as post,
        caplog.at_level("ERROR", logger="psynet"),
    ):
        posted = recruiter.reward_bonus(participant, amount=0.25, reason="completed")

    post.assert_not_called()
    assert "lab_recruiter_auth_token is not set" in caplog.text
    assert not posted


def test_lab_recruiter_token_prefix_is_normalized():
    recruiter = make_lab_recruiter(token="Token config-secret")
    participant = make_lab_participant()

    with patch("psynet.recruiters.requests.post") as post:
        recruiter.reward_bonus(participant, amount=0.25, reason="completed")

    assert post.call_args.kwargs["headers"] == {"Authorization": "Token config-secret"}


def test_lab_recruiter_reward_bonus_logs_http_error(caplog):
    from requests import HTTPError

    recruiter = make_lab_recruiter()
    participant = make_lab_participant()

    with (
        patch("psynet.recruiters.requests.post") as post,
        caplog.at_level("ERROR", logger="psynet"),
    ):
        post.return_value.raise_for_status.side_effect = HTTPError("bad response")
        posted = recruiter.reward_bonus(participant, amount=0.25, reason="completed")

    assert not posted
    assert "Lab Recruiter completion POST" in caplog.text
    assert participant.bonus is None


def test_lab_recruiter_validate_config_requires_token_outside_debug():
    make_lab_recruiter(token="abc123").validate_config(mode="live")
    with pytest.raises(ValueError, match="lab_recruiter_auth_token must be set"):
        make_lab_recruiter(token="").validate_config(mode="live")
    make_lab_recruiter(token="").validate_config(mode="debug")


@pytest.mark.parametrize("status", ["approved", "bad_data", "did_not_attend"])
def test_lab_recruiter_after_submission_complete_posts_zero_bonus_once(status):
    recruiter = make_lab_recruiter()
    participant = make_lab_participant()
    participant.status = status
    experiment = MagicMock()
    experiment.bonus_reason.return_value = "Thank you"

    with patch.object(recruiter, "reward_bonus", return_value=True) as reward_bonus:
        recruiter.after_submission_complete(experiment, participant)
        reward_bonus.assert_called_once_with(participant, 0, "Thank you")
        assert participant.bonus == 0

        recruiter.after_submission_complete(experiment, participant)
        reward_bonus.assert_called_once()


def test_lab_recruiter_after_submission_complete_ignores_other_statuses():
    recruiter = make_lab_recruiter()
    participant = make_lab_participant()
    participant.status = "working"

    with patch.object(recruiter, "reward_bonus") as reward_bonus:
        recruiter.after_submission_complete(MagicMock(), participant)

    reward_bonus.assert_not_called()
    assert participant.bonus is None


def test_experiment_submission_complete_dispatches_recruiter_hook(monkeypatch):
    from dallinger.experiment import Experiment as DallingerExperiment

    from psynet.experiment import Experiment

    recruiter = make_lab_recruiter()
    recruiter.after_submission_complete = MagicMock()
    participant = MagicMock()
    participant.recruiter = recruiter
    parent_hook = MagicMock()
    monkeypatch.setattr(
        DallingerExperiment, "on_recruiter_submission_complete", parent_hook
    )

    experiment = Experiment.__new__(Experiment)
    event = {"timestamp": "2026-08-18T00:00:00Z"}
    experiment.on_recruiter_submission_complete(participant, event)

    parent_hook.assert_called_once_with(participant, event)
    recruiter.after_submission_complete.assert_called_once_with(experiment, participant)


def test_rejected_consent_dispatches_recruiter_hook():
    from psynet.end import RejectedConsentLogic

    recruiter = make_lab_recruiter()
    recruiter.after_rejected_consent = MagicMock()
    experiment = MagicMock()
    experiment.recruiter = recruiter
    experiment.with_lucid_recruitment.return_value = False
    participant = MagicMock()

    RejectedConsentLogic().before_debrief(experiment, participant)

    participant.fail.assert_called_once_with()
    recruiter.after_rejected_consent.assert_called_once_with(experiment, participant)
