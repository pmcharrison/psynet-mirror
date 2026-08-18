import json
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import dallinger.experiment
import dallinger.recruiters
import pytest
from dallinger.prolific import ProlificServiceException

from psynet.participant import Participant
from psynet.recruiters import (
    PROLIFIC_SCREEN_OUT_ACTION,
    PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    PaymentDecision,
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


def test_completion_codes_unchanged_when_unsuccessful_payment_disabled():
    config = make_config(prolific_pay_unsuccessful=False)
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        codes = recruiter.completion_codes_and_actions

    assert [code["code_type"] for code in codes] == ["DEFAULT"]


def test_completion_codes_include_unsuccessful_code_with_default_payment():
    # The feature is on by default, with a fixed reward of 0.25.
    config = make_config(prolific_screen_out_slots=70)
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        codes = recruiter.completion_codes_and_actions

    assert [code["code_type"] for code in codes] == [
        "DEFAULT",
        PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    ]
    assert codes[-1]["actions"][0]["fixed_screen_out_reward"] == 25


def test_default_payment_rejected_when_base_payment_too_low():
    # The default fixed reward (0.25) must be strictly below base_payment,
    # so cheap studies must set prolific_unsuccessful_base_payment
    # explicitly or disable the feature.
    config = make_config(recruiter="prolific", base_payment=0.20)
    with pytest.raises(ValueError, match="less than"):
        PsyNetProlificRecruiterMixin.check_screen_out_config(config)


def test_completion_codes_include_unsuccessful_screen_out_code():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_screen_out_slots=70
    )
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
            "slots": 70,
        }
    ]
    assert unsuccessful["code"]


def test_completion_codes_require_explicit_screen_out_slots():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    recruiter = make_prolific_recruiter(config)

    with patch("psynet.recruiters.get_config", return_value=config):
        with pytest.raises(ValueError, match="prolific_screen_out_slots"):
            recruiter.completion_codes_and_actions


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
        prolific_screen_out_slots=10,
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
        (True, True, "submit"),
        (True, False, "return_for_bonus"),
        (False, True, "submit"),
        (False, False, "submit"),
    ],
)
def test_release_participant_branching(failed, payment_configured, expected):
    config = make_config(
        **(
            {"prolific_unsuccessful_base_payment": 0.50}
            if payment_configured
            else {"prolific_pay_unsuccessful": False}
        )
    )
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(failed=failed)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(recruiter, "submit_assignment") as submit:
            with patch.object(
                recruiter, "request_return_for_bonus"
            ) as return_for_bonus:
                recruiter.release_participant(MagicMock(), participant)

    if expected == "submit":
        submit.assert_called_once()
        return_for_bonus.assert_not_called()
    else:
        return_for_bonus.assert_called_once_with(participant)
        submit.assert_not_called()


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
        **(
            {"prolific_unsuccessful_base_payment": 0.50}
            if payment_configured
            else {"prolific_pay_unsuccessful": False}
        )
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


@pytest.mark.parametrize(
    "payment_enabled,failed,complete,expect_fail",
    [
        (True, False, False, True),  # errored mid-experiment: mark failed
        (True, True, False, False),  # already failed: leave as is
        (True, False, True, False),  # already complete: leave as is
        (False, False, False, False),  # feature disabled: leave as is
    ],
)
def test_on_error_page_marks_participant_failed(
    payment_enabled, failed, complete, expect_fail
):
    config = make_config(
        **(
            {"prolific_unsuccessful_base_payment": 0.20}
            if payment_enabled
            else {"prolific_pay_unsuccessful": False}
        )
    )
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(failed=failed, complete=complete)

    with patch("psynet.recruiters.get_config", return_value=config):
        recruiter.on_error_page(participant)

    if expect_fail:
        participant.fail.assert_called_once_with("error_page")
    else:
        participant.fail.assert_not_called()


def _identity_translator(context, message):
    return message


def render_error_page_html(recruiter, config, assignment_id, participant):
    with patch("psynet.recruiters.get_config", return_value=config):
        with patch(
            "psynet.recruiters.get_translator", return_value=_identity_translator
        ):
            with patch(
                "psynet.recruiters.latest_participant_for_assignment",
                return_value=participant,
            ):
                with patch.object(
                    recruiter,
                    "external_submission_url",
                    return_value="https://app.prolific.com/submissions/complete?cc=UNSUCCESSFUL-CODE",
                ) as external_url:
                    html = recruiter.error_page_content(assignment_id=assignment_id)
    return str(html), external_url


def test_error_page_content_offers_submit_button_when_screen_out_enabled():
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(id=42)

    html, external_url = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=participant
    )

    assert 'id="prolific-unsuccessful-submit"' in html
    assert "Submit to Prolific" in html
    assert "/prolific-submission-listener" in html
    assert "assignment-1" in html
    assert "42" in html
    assert "https://app.prolific.com/submissions/complete?cc=UNSUCCESSFUL-CODE" in html
    assert "send the researcher a message" not in html
    external_url.assert_called_once_with(code_type=PROLIFIC_UNSUCCESSFUL_CODE_TYPE)


def test_error_page_content_asks_to_message_when_screen_out_disabled():
    config = make_config(prolific_pay_unsuccessful=False)
    recruiter = make_prolific_recruiter(config)

    html, external_url = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=MagicMock(id=42)
    )

    assert "prolific-unsuccessful-submit" not in html
    assert "send the researcher a message" in html
    external_url.assert_not_called()


@pytest.mark.parametrize(
    "assignment_id,participant",
    [
        (None, MagicMock(id=42)),
        ("", MagicMock(id=42)),
        ("assignment-1", None),
    ],
)
def test_error_page_content_falls_back_without_assignment_or_participant(
    assignment_id, participant
):
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)

    html, external_url = render_error_page_html(
        recruiter, config, assignment_id=assignment_id, participant=participant
    )

    assert "prolific-unsuccessful-submit" not in html
    assert "send the researcher a message" in html
    external_url.assert_not_called()


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


def test_recruiter_exit_info_returns_none_when_payment_disabled():
    from psynet.experiment import Experiment

    config = make_config(prolific_pay_unsuccessful=False)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        assert Experiment.recruiter_exit_info(Experiment, participant) is None


class PaymentHarness:
    from psynet.experiment import Experiment as _Experiment

    base_payment = 1.00
    decide_and_record_payment = _Experiment.decide_and_record_payment
    pay_decided_bonus = _Experiment.pay_decided_bonus
    _mark_payment_settled = _Experiment._mark_payment_settled
    on_recruiter_submission_complete = _Experiment.on_recruiter_submission_complete

    def __init__(self):
        self.recruit_calls = 0
        self.submission_successful_calls = []

    def apply_payment_caps(self, participant, bonus):
        return bonus

    def bonus_reason(self):
        return "thanks"

    def submission_successful(self, participant):
        self.submission_successful_calls.append(participant)

    def recruit(self):
        self.recruit_calls += 1


def decide_for(participant, config):
    with patch("psynet.recruiters.get_config", return_value=config):
        return participant.recruiter.decide_payment(
            participant, experiment=PaymentHarness()
        )


def decided_bonus(participant, config):
    return decide_for(participant, config).bonus


def prepare_payout_participant(participant):
    participant.id = 7
    participant.bonus = None
    participant.end_time = None
    participant.assignment_id = "assignment-1"
    participant.payment_settled = False
    participant.unpaid_bonus = 0.0
    participant.recruiter.nickname = "prolific"
    participant.recruiter.approve_hit = MagicMock(return_value=True)
    participant.recruiter.reward_bonus = MagicMock()
    return participant


def test_default_recruiter_decide_payment_uses_full_study_base():
    from psynet.recruiters import HotAirRecruiter

    recruiter = object.__new__(HotAirRecruiter)
    participant = MagicMock(failed=False, status="submitted")
    participant.calculate_reward.return_value = 2.50

    decision = recruiter.decide_payment(participant, experiment=PaymentHarness())

    assert decision == PaymentDecision(
        status="approved",
        platform_base=1.00,
        bonus=1.50,
    )


def test_default_recruiter_treats_failed_participant_as_approved():
    from psynet.recruiters import HotAirRecruiter

    recruiter = object.__new__(HotAirRecruiter)
    participant = MagicMock(failed=True, status="submitted")
    participant.calculate_reward.return_value = 2.50

    decision = recruiter.decide_payment(participant, experiment=PaymentHarness())

    assert decision.status == "approved"
    assert decision.platform_base == 1.00
    assert decision.bonus == 1.50


def test_decide_payment_is_pure():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(
        config, failed=True, status="submitted"
    )
    participant.base_pay = 1.00
    participant.base_payment = 1.00

    decision = decide_for(participant, config)

    assert decision == PaymentDecision(
        status="screened_out",
        platform_base=0.50,
        bonus=2.00,
    )
    assert participant.status == "submitted"
    assert participant.base_payment == 1.00
    assert participant.base_pay == 1.00


def test_record_payment_writes_status_and_platform_base():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(
        config, failed=True, status="submitted"
    )
    participant.bonus = None
    decision = decide_for(participant, config)

    participant.recruiter.record_payment(participant, decision)

    assert participant.status == "screened_out"
    assert participant.base_pay == 0.50
    assert participant.base_payment == 0.50
    assert participant.bonus is None


def test_decide_payment_tops_up_unsuccessful_participant():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=True
    )
    participant = make_participant_with_recruiter(config, failed=True)
    assert decided_bonus(participant, config) == 2.00


def test_decide_payment_topup_never_negative():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=True
    )
    participant = make_participant_with_recruiter(config, failed=True)
    participant.calculate_reward.return_value = 0.20
    assert decided_bonus(participant, config) == 0.00


def test_decide_payment_without_topup_pays_only_performance_reward():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=False
    )
    participant = make_participant_with_recruiter(config, failed=True)
    assert decided_bonus(participant, config) == 0.30


def test_decide_payment_subtracts_base_payment_for_successful_participant():
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=False)
    assert decided_bonus(participant, config) == 1.50


def test_decide_payment_subtracts_base_for_failed_participant_with_feature_disabled():
    config = make_config(prolific_pay_unsuccessful=False)
    participant = make_participant_with_recruiter(config, failed=True)
    assert decided_bonus(participant, config) == 1.50


def test_decide_payment_never_negative():
    config = make_config()
    participant = make_participant_with_recruiter(config, failed=False)
    participant.calculate_reward.return_value = 0.20
    assert decided_bonus(participant, config) == 0.00


def test_decide_payment_uses_screen_out_base_when_status_already_screened_out():
    config = make_config(
        prolific_unsuccessful_base_payment=0.50, prolific_unsuccessful_topup=True
    )
    participant = make_participant_with_recruiter(
        config, failed=True, status="screened_out"
    )
    assert decided_bonus(participant, config) == 2.00


def test_decide_payment_pays_full_reward_when_status_is_returned():
    config = make_config(prolific_pay_unsuccessful=False)
    participant = make_participant_with_recruiter(
        config, failed=True, status="returned"
    )
    assert decided_bonus(participant, config) == 2.50


def test_on_recruiter_submission_complete_records_and_pays_screen_out():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="submitted")
    )
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(dallinger.experiment.Experiment, "data_check") as data_check:
            with patch.object(
                dallinger.experiment.Experiment, "on_recruiter_submission_complete"
            ) as dallinger_handler:
                harness.on_recruiter_submission_complete(
                    participant, {"timestamp": "2026-01-01"}
                )

    data_check.assert_not_called()
    dallinger_handler.assert_not_called()
    assert participant.status == "screened_out"
    assert participant.base_payment == 0.25
    assert participant.base_pay == 0.25
    assert participant.end_time == "2026-01-01"
    assert participant.bonus == 2.25
    assert participant.payment_settled is True
    participant.recruiter.approve_hit.assert_called_once_with("assignment-1")
    participant.recruiter.reward_bonus.assert_called_once()
    assert harness.recruit_calls == 1
    assert harness.submission_successful_calls == [participant]


def test_on_recruiter_submission_complete_records_platform_base_before_caps():
    config = make_config(
        prolific_unsuccessful_base_payment=0.25, prolific_unsuccessful_topup=True
    )
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="submitted")
    )
    participant.calculate_reward.return_value = 1.00
    participant.performance_reward = 0.0
    participant.base_pay = 1.00
    participant.base_payment = 1.00

    observed = {}

    class CapHarness(PaymentHarness):
        def apply_payment_caps(self, participant, bonus):
            observed["base_payment"] = participant.base_payment
            observed["base_pay"] = participant.base_pay
            paid = (participant.base_payment or 0.0) + (participant.bonus or 0.0)
            cap = 1.10
            if paid + bonus > cap:
                return round(cap - paid, 2)
            return bonus

    with patch("psynet.recruiters.get_config", return_value=config):
        CapHarness().on_recruiter_submission_complete(participant, event=None)

    assert observed["base_payment"] == 0.25
    assert observed["base_pay"] == 0.25
    assert participant.bonus == 0.75
    assert participant.status == "screened_out"


def test_on_recruiter_submission_complete_pays_successful_participant():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.status == "approved"
    assert participant.base_payment == 1.00
    assert participant.bonus == 1.50
    assert participant.payment_settled is True
    participant.recruiter.reward_bonus.assert_called_once()


def test_on_recruiter_submission_complete_skips_unexpected_status():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="working")
    )
    participant.base_payment = 1.00
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.status == "working"
    assert participant.base_payment == 1.00
    assert participant.bonus is None
    assert participant.payment_settled is False
    participant.recruiter.reward_bonus.assert_not_called()
    assert harness.recruit_calls == 0


def test_on_recruiter_submission_complete_retries_when_not_settled():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="screened_out")
    )
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.bonus == 2.25
    assert participant.payment_settled is True
    participant.recruiter.reward_bonus.assert_called_once()
    assert harness.recruit_calls == 1


def test_on_recruiter_submission_complete_skips_when_settled():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="submitted")
    )
    participant.payment_settled = True
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    participant.recruiter.reward_bonus.assert_not_called()
    assert harness.recruit_calls == 0
    assert participant.status == "submitted"


def test_pay_decided_bonus_skips_caps_when_already_settled():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    participant.payment_settled = True
    participant.bonus = 1.50
    harness = PaymentHarness()
    cap_calls = []
    harness.apply_payment_caps = lambda p, b: cap_calls.append(b) or b
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    assert harness.pay_decided_bonus(participant, decision) is True
    assert cap_calls == []
    participant.recruiter.reward_bonus.assert_not_called()


def test_pay_decided_bonus_leaves_unsettled_when_transfer_fails():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    assert harness.pay_decided_bonus(participant, decision) is False
    assert participant.bonus is None
    assert participant.payment_settled is False


def test_pay_decided_bonus_treats_none_transfer_as_success():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    participant.recruiter.reward_bonus.return_value = None
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    assert harness.pay_decided_bonus(participant, decision) is True
    assert participant.bonus == 1.50
    assert participant.payment_settled is True


def test_reward_and_set_bonus_uses_payment_decision():
    config = make_config(prolific_pay_unsuccessful=False)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="returned")
    )
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch("psynet.experiment.get_experiment", return_value=harness):
            PsyNetProlificRecruiterMixin.reward_and_set_bonus(participant)

    assert participant.status == "returned"
    assert participant.base_payment == 0.0
    assert participant.bonus == 2.50
    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.recruiter.reward_bonus.call_args.args[2] == (
        "Partial payment for incomplete participation"
    )


def make_prolific_deploy_config(**overrides):
    return make_config(recruiter="prolific", **overrides)


def test_check_screen_out_config_rejects_payment_at_or_above_base_payment():
    config = make_prolific_deploy_config(
        prolific_unsuccessful_base_payment=1.00, prolific_screen_out_slots=10
    )
    with pytest.raises(ValueError, match="less than"):
        PsyNetProlificRecruiterMixin.check_screen_out_config(config)

    PsyNetProlificRecruiterMixin.check_screen_out_config(
        make_prolific_deploy_config(
            prolific_unsuccessful_base_payment=0.99, prolific_screen_out_slots=10
        )
    )


def test_check_screen_out_config_requires_screen_out_slots():
    with pytest.raises(ValueError, match="prolific_screen_out_slots"):
        PsyNetProlificRecruiterMixin.check_screen_out_config(
            make_prolific_deploy_config()
        )

    # Passes with slots set...
    PsyNetProlificRecruiterMixin.check_screen_out_config(
        make_prolific_deploy_config(prolific_screen_out_slots=10)
    )
    # ...when the feature is disabled...
    PsyNetProlificRecruiterMixin.check_screen_out_config(
        make_prolific_deploy_config(prolific_pay_unsuccessful=False)
    )
    # ...and for non-Prolific recruiters.
    PsyNetProlificRecruiterMixin.check_screen_out_config(
        make_config(recruiter="hotair")
    )
    PsyNetProlificRecruiterMixin.check_screen_out_config(make_config())


def test_check_config_rejects_stale_error_page_override():
    from psynet.experiment import Experiment

    class ExpWithStaleOverride(Experiment):
        def error_page_content__prolific(self):
            return "custom"

    with pytest.raises(RuntimeError, match="no longer supported"):
        ExpWithStaleOverride.check_stale_error_page_override()

    # The base class (no override) passes.
    Experiment.check_stale_error_page_override()


def test_check_unused_dallinger_quality_checks_rejects_overrides():
    from psynet.experiment import Experiment

    class ExpWithDataCheck(Experiment):
        def data_check(self, participant):
            return True

        def attention_check(self, participant):
            return True

    with pytest.raises(RuntimeError, match="data_check"):
        ExpWithDataCheck.check_unused_dallinger_quality_checks()

    Experiment.check_unused_dallinger_quality_checks()


def test_check_stale_bonus_override_rejects_experiment_bonus():
    from psynet.experiment import Experiment

    class ExpWithBonus(Experiment):
        def bonus(self, participant):
            return 1.0

    with pytest.raises(RuntimeError, match="decide_payment"):
        ExpWithBonus.check_stale_bonus_override()

    Experiment.check_stale_bonus_override()


class PaymentCapHarness:
    from psynet.experiment import Experiment as _Experiment

    apply_payment_caps = _Experiment.apply_payment_caps
    pay_decided_bonus = _Experiment.pay_decided_bonus
    _mark_payment_settled = _Experiment._mark_payment_settled

    def __init__(
        self, *, spent=0.0, outstanding=0.0, hard_max=1100.0, max_participant=25.0
    ):
        self.spent = spent
        self.outstanding = outstanding
        self.var = SimpleNamespace(
            hard_max_experiment_payment=hard_max,
            max_participant_payment=max_participant,
            hard_max_experiment_payment_email_sent=False,
        )
        self.hard_max_emails = 0

    def amount_spent(self):
        return self.spent

    def outstanding_base_payments(self):
        return self.outstanding

    def ensure_hard_max_experiment_payment_email_sent(self):
        self.hard_max_emails += 1
        self.var.hard_max_experiment_payment_email_sent = True


def test_apply_payment_caps_withholds_bonus_at_hard_max():
    harness = PaymentCapHarness(spent=9.50, outstanding=0.0, hard_max=10.0)
    participant = MagicMock(id=1, unpaid_bonus=0.0)

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.0
    assert participant.unpaid_bonus == 1.00
    assert harness.hard_max_emails == 1
    participant.send_email_max_payment_reached.assert_not_called()


def test_apply_payment_caps_does_not_withhold_once_under_hard_max():
    harness = PaymentCapHarness(spent=8.00, outstanding=0.0, hard_max=10.0)
    participant = MagicMock(id=1)
    participant.amount_paid.return_value = 1.00

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 1.00
    assert harness.hard_max_emails == 0


def test_apply_payment_caps_clips_to_max_participant_payment():
    harness = PaymentCapHarness(max_participant=5.00)
    participant = MagicMock(id=1)
    participant.amount_paid.return_value = 4.50

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.50
    participant.send_email_max_payment_reached.assert_called_once_with(
        harness, 1.00, 0.50
    )


def test_apply_payment_caps_does_not_add_outstanding_bases():
    harness = PaymentCapHarness(spent=9.50, outstanding=5.0, hard_max=10.0)
    participant = MagicMock(id=1)
    participant.amount_paid.return_value = 1.00

    result = harness.apply_payment_caps(participant, 0.40)

    assert result == 0.40
    assert harness.hard_max_emails == 0


def test_pay_decided_bonus_withholds_at_hard_max_and_settles():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)
    participant = MagicMock(id=1, payment_settled=False, unpaid_bonus=0.0, bonus=None)
    participant.recruiter.reward_bonus = MagicMock()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.00)

    assert harness.pay_decided_bonus(participant, decision) is True
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.unpaid_bonus == 1.00
    assert participant.bonus is None
    assert participant.payment_settled is True


def test_experiment_bonus_raises():
    from psynet.experiment import Experiment

    with pytest.raises(NotImplementedError, match="decide_payment"):
        Experiment.bonus(Experiment, MagicMock())


def test_open_recruitment_reraises_with_hint_when_screen_out_enabled(caplog):
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)

    rejection = ProlificServiceException("Error creating study: bad request")

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(
            dallinger.recruiters.ProlificRecruiter,
            "open_recruitment",
            side_effect=rejection,
        ) as super_open:
            with pytest.raises(ProlificServiceException):
                # Call the mixin implementation directly: the ProlificRecruiter
                # subclass adds Slack notification on top, which needs a
                # running experiment.
                PsyNetProlificRecruiterMixin.open_recruitment(recruiter, n=5)

    assert super_open.call_count == 1
    assert "prolific_pay_unsuccessful" in caplog.text


def test_open_recruitment_no_hint_when_screen_out_disabled(caplog):
    config = make_config(prolific_pay_unsuccessful=False)
    recruiter = make_prolific_recruiter(config)

    rejection = ProlificServiceException("Error creating study: bad request")

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(
            dallinger.recruiters.ProlificRecruiter,
            "open_recruitment",
            side_effect=rejection,
        ):
            with pytest.raises(ProlificServiceException):
                PsyNetProlificRecruiterMixin.open_recruitment(recruiter, n=5)

    assert "prolific_pay_unsuccessful" not in caplog.text
