import json
from unittest.mock import MagicMock, PropertyMock, patch

import dallinger.recruiters
import pytest
from dallinger.prolific import ProlificServiceException

from psynet.participant import Participant
from psynet.recruiters import (
    PROLIFIC_SCREEN_OUT_ACTION,
    PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
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


# Prolific UNSUCCESSFUL completion code (fixed screen-out payments)

_UNSET = object()


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=_UNSET):
        if key in self.values:
            return self.values[key]
        if default is _UNSET:
            raise KeyError(key)
        return default


def make_config(**overrides):
    values = {
        "id": "test-experiment",
        "prolific_completion_config": "{}",
        "initial_recruitment_size": 7,
        "base_payment": 1.00,
    }
    values.update(overrides)
    return FakeConfig(**values)


def make_prolific_recruiter(config):
    recruiter = object.__new__(ProlificRecruiter)
    recruiter.config = config
    return recruiter


def test_completion_codes_unchanged_when_unsuccessful_payment_not_configured():
    config = make_config()
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        codes = recruiter.completion_codes_and_actions

    assert [code["code_type"] for code in codes] == ["DEFAULT"]


def test_completion_codes_include_unsuccessful_screen_out_code():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        codes = recruiter.completion_codes_and_actions

    assert [code["code_type"] for code in codes] == [
        "DEFAULT",
        PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    ]
    unsuccessful = codes[-1]
    assert unsuccessful["actor"] == "participant"
    assert unsuccessful["actions"] == [
        {
            "action": PROLIFIC_SCREEN_OUT_ACTION,
            "fixed_screen_out_reward": 50,
            # Defaults to 10 * initial_recruitment_size
            "slots": 70,
        }
    ]
    assert unsuccessful["code"]


def test_completion_codes_respect_explicit_screen_out_slots():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_screen_out_slots=25
    )
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        codes = recruiter.completion_codes_and_actions

    assert codes[-1]["actions"][0]["slots"] == 25


def test_completion_codes_reject_conflicting_screen_out_action():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50,
        prolific_completion_config=json.dumps(
            {
                "CUSTOM_SCREEN_OUT": {
                    "actor": "participant",
                    "actions": [
                        {
                            "action": PROLIFIC_SCREEN_OUT_ACTION,
                            "fixed_screen_out_reward": 30,
                            "slots": 5,
                        }
                    ],
                }
            }
        ),
    )
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        with pytest.raises(RuntimeError, match="only supports one completion code"):
            recruiter.completion_codes_and_actions


@pytest.mark.parametrize(
    "failed,payment_configured,expected",
    [
        (True, True, "approve"),
        (True, False, "reject"),
        (False, True, "approve"),
        (False, False, "approve"),
    ],
)
def test_release_participant_branching(failed, payment_configured, expected):
    config = make_config(
        prolific_unsuccessful_base_payment=0.50 if payment_configured else None
    )
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(failed=failed)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(recruiter, "approve_assignment") as approve:
            with patch.object(recruiter, "reject_assignment") as reject:
                recruiter.release_participant(MagicMock(), participant)

    if expected == "approve":
        approve.assert_called_once()
        reject.assert_not_called()
    else:
        reject.assert_called_once_with(participant)
        approve.assert_not_called()


@pytest.mark.parametrize(
    "failed,payment_configured,expect_skipped",
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
def test_approve_hit_skips_screened_out_participants(
    failed, payment_configured, expect_skipped
):
    config = make_config(
        prolific_unsuccessful_base_payment=0.50 if payment_configured else None
    )
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(failed=failed)

    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.first.return_value = participant

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(Participant, "query", query):
            with patch.object(
                dallinger.recruiters.ProlificRecruiter, "approve_hit"
            ) as super_approve:
                result = recruiter.approve_hit("assignment-1")

    if expect_skipped:
        super_approve.assert_not_called()
        assert result is True
    else:
        super_approve.assert_called_once_with("assignment-1")


def make_participant_with_recruiter(config, failed=True, status="working"):
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock()
    participant.failed = failed
    participant.status = status
    participant.recruiter = recruiter
    participant.calculate_reward.return_value = 2.50
    participant.performance_reward = 0.30
    return participant


def test_recruiter_exit_info_returns_unsuccessful_code_type_for_failed_participant():
    from psynet.experiment import Experiment

    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        assert (
            Experiment.recruiter_exit_info(Experiment, participant)
            == PROLIFIC_UNSUCCESSFUL_CODE_TYPE
        )


def test_recruiter_exit_info_returns_none_for_successful_participant():
    from psynet.experiment import Experiment

    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=False)

    with patch("psynet.recruiters.get_config", return_value=config):
        assert Experiment.recruiter_exit_info(Experiment, participant) is None


def test_recruiter_exit_info_returns_none_when_payment_not_configured():
    from psynet.experiment import Experiment

    config = make_config()
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        assert Experiment.recruiter_exit_info(Experiment, participant) is None


class BonusHarness:
    from psynet.experiment import Experiment as _Experiment

    base_payment = 1.00
    bonus = _Experiment.bonus

    def check_bonus(self, reward, participant):
        return reward


def bonus_for(participant, config):
    with patch("psynet.recruiters.get_config", return_value=config):
        with patch("psynet.experiment.get_config", return_value=config):
            return BonusHarness().bonus(participant)


def test_bonus_tops_up_unsuccessful_participant():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=True
    )
    participant = make_participant_with_recruiter(config, failed=True)
    # Accumulated reward 2.50 minus the 0.50 screen-out payment
    assert bonus_for(participant, config) == 2.00


def test_bonus_topup_never_negative():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=True
    )
    participant = make_participant_with_recruiter(config, failed=True)
    participant.calculate_reward.return_value = 0.20
    assert bonus_for(participant, config) == 0.00


def test_bonus_without_topup_pays_only_performance_reward():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=False
    )
    participant = make_participant_with_recruiter(config, failed=True)
    assert bonus_for(participant, config) == 0.30


def test_bonus_subtracts_base_payment_for_successful_participant():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=False)
    assert bonus_for(participant, config) == 1.50


def test_bonus_subtracts_base_payment_for_failed_participant_without_feature():
    config = make_config()
    participant = make_participant_with_recruiter(config, failed=True)
    assert bonus_for(participant, config) == 1.50


def test_check_unsuccessful_base_payment_must_be_less_than_base_payment():
    config = make_config(prolific_unsuccessful_base_payment=1.00)
    with pytest.raises(ValueError, match="must be less than"):
        PsyNetProlificRecruiterMixin.check_unsuccessful_base_payment(config)

    PsyNetProlificRecruiterMixin.check_unsuccessful_base_payment(
        make_config(prolific_unsuccessful_base_payment=0.99)
    )
    PsyNetProlificRecruiterMixin.check_unsuccessful_base_payment(make_config())
