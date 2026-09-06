import json
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import dallinger.experiment
import dallinger.recruiters
import pytest
from dallinger.prolific import ProlificServiceException

from psynet.participant import (
    BONUS_PAY_IN_PROGRESS,
    BONUS_STATUS_CAPPED,
    BONUS_STATUS_DISMISSED,
    BONUS_STATUS_NOT_DUE_YET,
    BONUS_STATUS_SUCCESS,
    BONUS_STATUS_UNCONFIRMED,
    NO_BONUS_ATTEMPT_RESULT,
    Participant,
    bonus_is_settled,
    bonus_needs_review,
    bonus_transfer_already_claimed,
    display_bonus_status,
    review_bonus_pay_in_progress,
)
from psynet.recruiters import (
    PROLIFIC_SCREEN_OUT_ACTION,
    PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    BaseLabRecruiter,
    BaseLucidRecruiter,
    EarlyExitConfirmation,
    EarlyExitContext,
    EarlyExitPath,
    EarlyExitPlan,
    HotAirRecruiter,
    MTurkRecruiter,
    PaymentDecision,
    ProlificRecruiter,
    PsyNetProlificRecruiterMixin,
    PsyNetRecruiterMixin,
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
        "currency": "$",
        "min_reward_for_paid_early_exit": 0.20,
        "prolific_pay_unsuccessful": True,
        "prolific_unsuccessful_base_payment": 0.25,
        "prolific_unsuccessful_topup": True,
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
    "path,expected_method",
    [
        (EarlyExitPath.SCREEN_OUT, "submit_assignment"),
        (EarlyExitPath.RETURN_FOR_BONUS, "request_return_for_bonus"),
        (
            EarlyExitPath.RETURN_WITHOUT_PAYMENT,
            "release_early_exit_without_payment",
        ),
    ],
)
def test_prolific_release_follows_the_executed_plan(path, expected_method):
    recruiter = make_prolific_recruiter(make_config())
    participant = MagicMock(
        early_exited=True,
        early_exit_plan=_early_exit_test_plan(path).mark_executed().to_dict(),
    )

    with (
        patch.object(recruiter, "submit_assignment") as submit,
        patch.object(recruiter, "request_return_for_bonus") as return_for_bonus,
        patch.object(
            recruiter, "release_early_exit_without_payment"
        ) as without_payment,
    ):
        recruiter.release_participant(MagicMock(), participant)

    methods = {
        "submit_assignment": submit,
        "request_return_for_bonus": return_for_bonus,
        "release_early_exit_without_payment": without_payment,
    }
    for name, method in methods.items():
        assert method.call_count == (1 if name == expected_method else 0)


@pytest.mark.parametrize(
    "status,expect_skipped",
    [
        ("screened_out", True),
        ("returned", True),
        ("approved", False),
        ("submitted", False),
    ],
)
def test_approve_hit_skips_when_status_is_not_approvable(status, expect_skipped):
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(status=status)

    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.first.return_value = participant

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


@pytest.mark.parametrize(
    "bonus_status,expect_skipped",
    [
        (BONUS_STATUS_NOT_DUE_YET, False),  # first pass: approve normally
        (BONUS_STATUS_UNCONFIRMED, True),  # replay: payment already handled
        (BONUS_STATUS_SUCCESS, True),
        (BONUS_STATUS_CAPPED, True),
        (BONUS_STATUS_DISMISSED, True),
    ],
)
def test_approve_hit_skips_submission_complete_replays(bonus_status, expect_skipped):
    """A submission-complete replay must not approve an already-approved
    submission: Prolific rejects it, producing spurious recruitment errors.
    """
    config = make_config(prolific_unsuccessful_base_payment=0.50)
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(status="submitted", bonus_status=bonus_status)

    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.first.return_value = participant

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
    participant.complete = False
    participant.status = status
    participant.recruiter = recruiter
    participant.calculate_reward.return_value = 2.50
    participant.performance_reward = 0.30
    participant.issued_completion_code_type = None
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus = None
    participant.bonus_attempt_detail = None
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


def make_error_page_participant(id=42, complete=False, issued=None):
    return MagicMock(id=id, complete=complete, issued_completion_code_type=issued)


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
    participant = make_error_page_participant()

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
    assert participant.issued_completion_code_type is None
    external_url.assert_called_once_with(code_type=PROLIFIC_UNSUCCESSFUL_CODE_TYPE)


def test_error_page_content_asks_to_message_when_screen_out_disabled():
    config = make_config(prolific_pay_unsuccessful=False)
    recruiter = make_prolific_recruiter(config)

    html, external_url = render_error_page_html(
        recruiter,
        config,
        assignment_id="assignment-1",
        participant=make_error_page_participant(),
    )

    assert "prolific-unsuccessful-submit" not in html
    assert "send the researcher a message" in html
    external_url.assert_not_called()


@pytest.mark.parametrize(
    "assignment_id,participant",
    [
        (None, make_error_page_participant()),
        ("", make_error_page_participant()),
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


def test_error_page_content_does_not_reclassify_complete_participant():
    """Rendering the error page for a complete participant must not offer the
    screen-out submit button or overwrite the issued completion code, which
    would reclassify a successful participant as screened-out on a
    submission-complete replay.
    """
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_error_page_participant(complete=True, issued="DEFAULT")

    html, external_url = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=participant
    )

    assert "prolific-unsuccessful-submit" not in html
    assert "send the researcher a message" in html
    assert participant.issued_completion_code_type == "DEFAULT"
    external_url.assert_not_called()


def test_error_page_content_does_not_overwrite_other_issued_code():
    # First issuance wins even for incomplete participants: whoever already
    # exited with the auto-approving code must not be re-stamped.
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_error_page_participant(complete=False, issued="DEFAULT")

    html, _ = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=participant
    )

    assert "prolific-unsuccessful-submit" not in html
    assert participant.issued_completion_code_type == "DEFAULT"


def test_error_page_content_keeps_button_on_rerender():
    # A participant who already submitted with UNSUCCESSFUL (e.g. reloading
    # the error page after the listener stamped the code) still sees the
    # submit button.
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_error_page_participant(issued=PROLIFIC_UNSUCCESSFUL_CODE_TYPE)

    html, _ = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=participant
    )

    assert 'id="prolific-unsuccessful-submit"' in html
    assert participant.issued_completion_code_type == PROLIFIC_UNSUCCESSFUL_CODE_TYPE


def test_error_page_render_does_not_change_decide_payment():
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_participant_with_recruiter(config, failed=False)
    participant.id = 42
    participant.complete = False

    html, _ = render_error_page_html(
        recruiter, config, assignment_id="assignment-1", participant=participant
    )

    assert 'id="prolific-unsuccessful-submit"' in html
    assert participant.issued_completion_code_type is None
    decision = decide_for(participant, config)
    assert decision.status == "approved"
    assert decision.platform_base == 1.00


def test_issue_unsuccessful_completion_code_stamps_failed_participant():
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        assert recruiter.issue_unsuccessful_completion_code(participant) is True
    assert participant.issued_completion_code_type == PROLIFIC_UNSUCCESSFUL_CODE_TYPE


def _early_exit_test_plan(path=EarlyExitPath.END_SESSION):
    return EarlyExitPlan.create(
        context=EarlyExitContext.VOLUNTARY,
        path=path,
        confirmation=EarlyExitConfirmation(
            title="Leave?",
            message="Your responses are saved.",
            confirm_label="Leave",
            cancel_label="Continue",
        ),
    )


def test_execute_early_exit_plan_marks_early_exited_and_fails():
    participant = MagicMock()
    participant.failed = False
    PsyNetRecruiterMixin().execute_early_exit_plan(
        MagicMock(), participant, _early_exit_test_plan()
    )
    assert participant.early_exited is True
    participant.module_state.mark_early_exited.assert_called_once()
    participant.fail.assert_called_once_with("early_exit")


def test_execute_early_exit_plan_skips_fail_when_already_failed():
    participant = MagicMock()
    participant.failed = True
    PsyNetRecruiterMixin().execute_early_exit_plan(
        MagicMock(), participant, _early_exit_test_plan()
    )
    assert participant.early_exited is True
    participant.fail.assert_not_called()


def _participant_for_early_exit(reward=0.50, performance_reward=0.0):
    participant = MagicMock()
    participant.calculate_reward.return_value = reward
    participant.performance_reward = performance_reward
    participant.failed = False
    participant.early_exit_plan = None
    return participant


@pytest.mark.parametrize(
    "recruiter_class, expected_path, expected_message",
    [
        (
            PsyNetRecruiterMixin,
            EarlyExitPath.END_SESSION,
            "responses so far will still be saved",
        ),
        (
            MTurkRecruiter,
            EarlyExitPath.SUBMIT_AND_APPROVE,
            "HIT payment",
        ),
        (
            PsyNetProlificRecruiterMixin,
            EarlyExitPath.SCREEN_OUT,
            "fixed early-exit payment",
        ),
        (
            BaseLucidRecruiter,
            EarlyExitPath.TERMINATE_PANEL_SESSION,
            "panel provider",
        ),
    ],
)
def test_recruiters_plan_their_early_exit_consequences(
    recruiter_class, expected_path, expected_message
):
    recruiter = object.__new__(recruiter_class)
    participant = _participant_for_early_exit()
    experiment = MagicMock()
    experiment.early_exit_allowed.return_value = True
    with (
        patch("psynet.recruiters.get_config", return_value=make_config()),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )

    assert plan.path is expected_path
    confirmation = plan.confirmation
    assert isinstance(confirmation, EarlyExitConfirmation)
    assert expected_message in confirmation.message
    assert confirmation.title == "Leave without finishing?"
    assert confirmation.confirm_label == "Leave"
    assert confirmation.cancel_label == "Continue"
    assert plan.status == "offered"
    assert plan.offer_id


def test_early_exit_plan_round_trips_through_participant_column_data():
    confirmation = EarlyExitConfirmation(
        title="Leave?",
        message="Your work is saved.",
        confirm_label="Leave",
        cancel_label="Continue",
    )
    plan = EarlyExitPlan.create(
        context=EarlyExitContext.VOLUNTARY,
        path=EarlyExitPath.SCREEN_OUT,
        confirmation=confirmation,
        quoted_amounts={"currency": "£", "fixed_minor": 20},
    )

    restored = EarlyExitPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert restored.to_dict()["path"] == "screen_out"
    assert restored.to_dict()["confirmation"]["message"] == "Your work is saved."


def test_participant_has_dedicated_early_exit_plan_column():
    assert "early_exit_plan" in Participant.__table__.columns


def test_early_exit_reward_threshold_does_not_block_lucid_termination():
    participant = MagicMock()
    participant.calculate_reward.return_value = 0.0
    with patch(
        "psynet.recruiters.get_config",
        return_value=make_config(min_reward_for_paid_early_exit=0.2),
    ):
        assert PsyNetRecruiterMixin().early_exit_allowed(participant) is False
    lucid = object.__new__(BaseLucidRecruiter)
    assert lucid.early_exit_allowed(participant) is True


def test_unpaid_recruiters_always_allow_early_exit():
    participant = _participant_for_early_exit(reward=0.0)
    hot_air = object.__new__(HotAirRecruiter)
    assert hot_air.early_exit_allowed(participant) is True


def test_prolific_early_exit_messages_cover_payment_pathways():
    participant = _participant_for_early_exit(reward=0.80)
    recruiter = object.__new__(PsyNetProlificRecruiterMixin)
    experiment = MagicMock()
    experiment.early_exit_allowed.return_value = True
    with (
        patch("psynet.recruiters.get_config", return_value=make_config()),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        topped_up = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )
    assert topped_up.path is EarlyExitPath.SCREEN_OUT
    assert topped_up.quoted_amounts == {
        "currency": "$",
        "earned_minor": 80,
        "fixed_minor": 25,
        "remainder_minor": 55,
    }
    topped_up_confirmation = topped_up.confirmation
    assert "£" not in topped_up_confirmation.message
    assert (
        "$0.25" in topped_up_confirmation.message
        and "$0.80" in topped_up_confirmation.message
    )

    with (
        patch(
            "psynet.recruiters.get_config",
            return_value=make_config(prolific_unsuccessful_topup=False),
        ),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        participant.performance_reward = 0.05
        no_topup = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )
    assert no_topup.path is EarlyExitPath.SCREEN_OUT
    assert "not be paid for additional time" in no_topup.confirmation.message
    assert "$0.05" in no_topup.confirmation.message

    with (
        patch(
            "psynet.recruiters.get_config",
            return_value=make_config(prolific_pay_unsuccessful=False),
        ),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        returned = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )
    assert returned.path is EarlyExitPath.RETURN_FOR_BONUS
    assert "return your Prolific submission" in returned.confirmation.message
    assert "$0.80" in returned.confirmation.message


@pytest.mark.parametrize(
    "recruiter_class, reward, expected_path, expected_decision",
    [
        (
            PsyNetProlificRecruiterMixin,
            0.80,
            EarlyExitPath.SCREEN_OUT,
            PaymentDecision(status="screened_out", platform_base=0.25, bonus=0.55),
        ),
        (
            MTurkRecruiter,
            1.80,
            EarlyExitPath.SUBMIT_AND_APPROVE,
            PaymentDecision(status="approved", platform_base=1.00, bonus=0.80),
        ),
    ],
)
def test_executed_plan_uses_the_amounts_shown_in_confirmation(
    recruiter_class, reward, expected_path, expected_decision
):
    participant = _participant_for_early_exit(reward=reward)
    recruiter = object.__new__(recruiter_class)
    experiment = MagicMock(base_payment=9.00)
    experiment.early_exit_allowed.return_value = True
    with (
        patch("psynet.recruiters.get_config", return_value=make_config()),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )
    assert plan.path is expected_path

    participant.early_exited = True
    participant.early_exit_plan = plan.mark_executed().to_dict()
    participant.calculate_reward.return_value = 99.00

    assert (
        recruiter.decide_payment(participant, experiment=experiment)
        == expected_decision
    )


def test_return_for_bonus_uses_the_planned_reward():
    participant = _participant_for_early_exit(reward=0.80)
    recruiter = object.__new__(PsyNetProlificRecruiterMixin)
    experiment = MagicMock()
    experiment.early_exit_allowed.return_value = True
    config = make_config(prolific_pay_unsuccessful=False)
    with (
        patch("psynet.recruiters.get_config", return_value=config),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )

    participant.early_exited = True
    participant.early_exit_plan = plan.mark_executed().to_dict()
    participant.calculate_reward.return_value = 99.00

    assert recruiter.decide_payment(
        participant, experiment=experiment
    ) == PaymentDecision(status="returned", platform_base=0.0, bonus=0.80)


def test_below_threshold_offers_unpaid_leave_with_amounts():
    participant = _participant_for_early_exit(reward=0.10)
    recruiter = object.__new__(PsyNetProlificRecruiterMixin)
    experiment = MagicMock()
    experiment.early_exit_allowed.return_value = False
    with (
        patch(
            "psynet.recruiters.get_config",
            return_value=make_config(currency="£", min_reward_for_paid_early_exit=0.20),
        ),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.VOLUNTARY
        )
    assert plan.path is EarlyExitPath.RETURN_WITHOUT_PAYMENT
    assert plan.quoted_amounts == {
        "currency": "£",
        "earned_minor": 10,
        "threshold_minor": 20,
    }
    confirmation = plan.confirmation
    assert confirmation.title == "Leave without finishing?"
    assert confirmation.confirm_label == "Leave without payment"
    assert confirmation.cancel_label == "Continue"
    assert "£0.10" in confirmation.message
    assert "£0.20" in confirmation.message


def test_error_recovery_plan_skips_reward_eligibility():
    participant = _participant_for_early_exit(reward=0.05)
    recruiter = object.__new__(PsyNetProlificRecruiterMixin)
    experiment = MagicMock()
    experiment.early_exit_allowed.side_effect = RuntimeError("reward boom")
    with (
        patch("psynet.recruiters.get_config", return_value=make_config()),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.ERROR_RECOVERY
        )
    assert plan.path is EarlyExitPath.SCREEN_OUT
    assert "fixed early-exit payment" in plan.confirmation.message
    experiment.early_exit_allowed.assert_not_called()


@pytest.mark.parametrize(
    "recruiter_class,recovered_reward,expected_path,expected_decision",
    [
        (
            PsyNetProlificRecruiterMixin,
            0.80,
            EarlyExitPath.SCREEN_OUT,
            PaymentDecision(status="screened_out", platform_base=0.25, bonus=0.55),
        ),
        (
            MTurkRecruiter,
            1.80,
            EarlyExitPath.SUBMIT_AND_APPROVE,
            PaymentDecision(status="approved", platform_base=1.00, bonus=0.80),
        ),
    ],
)
def test_error_recovery_plan_survives_reward_calculation_failure(
    recruiter_class,
    recovered_reward,
    expected_path,
    expected_decision,
    caplog,
):
    participant = _participant_for_early_exit()
    participant.calculate_reward.side_effect = RuntimeError("reward boom")
    recruiter = object.__new__(recruiter_class)
    experiment = MagicMock(base_payment=9.00)

    with (
        patch("psynet.recruiters.get_config", return_value=make_config()),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.ERROR_RECOVERY
        )
        participant.calculate_reward.side_effect = None
        participant.calculate_reward.return_value = recovered_reward
        participant.early_exited = True
        participant.early_exit_plan = plan.mark_executed().to_dict()
        decision = recruiter.decide_payment(participant, experiment=experiment)

    assert plan.path is expected_path
    assert plan.quoted_amounts_complete is False
    assert "without a reward quote" in caplog.text
    assert decision == expected_decision


def test_prolific_return_for_bonus_recovery_survives_reward_failure():
    participant = _participant_for_early_exit()
    participant.calculate_reward.side_effect = RuntimeError("reward boom")
    recruiter = object.__new__(PsyNetProlificRecruiterMixin)
    experiment = MagicMock()
    config = make_config(prolific_pay_unsuccessful=False)

    with (
        patch("psynet.recruiters.get_config", return_value=config),
        patch("psynet.recruiters.get_translator", return_value=_identity_translator),
    ):
        plan = recruiter.plan_early_exit(
            experiment, participant, EarlyExitContext.ERROR_RECOVERY
        )
        participant.calculate_reward.side_effect = None
        participant.calculate_reward.return_value = 0.80
        participant.early_exited = True
        participant.early_exit_plan = plan.mark_executed().to_dict()
        decision = recruiter.decide_payment(participant, experiment=experiment)

    assert plan.path is EarlyExitPath.RETURN_FOR_BONUS
    assert plan.quoted_amounts_complete is False
    assert decision == PaymentDecision(status="returned", platform_base=0.0, bonus=0.80)


def test_early_exit_route_executes_the_stored_plan():
    from flask import Flask

    from psynet.experiment import Experiment

    plan = EarlyExitPlan.create(
        context=EarlyExitContext.VOLUNTARY,
        path=EarlyExitPath.SCREEN_OUT,
        confirmation=EarlyExitConfirmation(
            title="Leave?",
            message="You will be screened out.",
            confirm_label="Leave",
            cancel_label="Continue",
        ),
    )
    participant = MagicMock()
    participant.early_exited = False
    participant.unique_id = "unique-1"
    participant.early_exit_plan = plan.to_dict()
    experiment = MagicMock()

    with (
        Flask(__name__).test_request_context(
            "/set_participant_as_early_exited/assign-1",
            method="POST",
            json={"offer_id": plan.offer_id},
        ),
        patch.object(
            Experiment,
            "get_participant_from_assignment_id",
            return_value=participant,
        ),
        patch("psynet.experiment.get_experiment", return_value=experiment),
        patch("psynet.experiment.success_response", return_value="ok") as success,
    ):
        assert Experiment.route_set_participant_as_early_exited("assign-1") == "ok"

    success.assert_called_once_with(release_url="/timeline?unique_id=unique-1")
    experiment.recruiter.execute_early_exit_plan.assert_called_once()
    called_experiment, called_participant, executed_plan = (
        experiment.recruiter.execute_early_exit_plan.call_args.args
    )
    assert called_experiment is experiment
    assert called_participant is participant
    assert executed_plan.path is EarlyExitPath.SCREEN_OUT
    assert participant.pending_redirect == "early_exit_release"
    assert participant.early_exit_plan["status"] == "executed"
    experiment.timeline.advance_page.assert_called_once_with(experiment, participant)


@pytest.mark.parametrize("payload", [{"offer_id": "stale-offer"}, []])
def test_early_exit_route_rejects_an_invalid_offer(payload):
    from flask import Flask

    from psynet.experiment import Experiment

    plan = EarlyExitPlan.create(
        context=EarlyExitContext.VOLUNTARY,
        path=EarlyExitPath.SCREEN_OUT,
        confirmation=EarlyExitConfirmation(
            title="Leave?",
            message="You will be screened out.",
            confirm_label="Leave",
            cancel_label="Continue",
        ),
    )
    participant = MagicMock(early_exited=False, early_exit_plan=plan.to_dict())
    experiment = MagicMock()

    with (
        Flask(__name__).test_request_context(
            "/set_participant_as_early_exited/assign-1",
            method="POST",
            json=payload,
        ),
        patch.object(
            Experiment,
            "get_participant_from_assignment_id",
            return_value=participant,
        ),
        patch("psynet.experiment.get_experiment", return_value=experiment),
        patch("psynet.experiment.error_response", return_value="stale") as error,
    ):
        assert Experiment.route_set_participant_as_early_exited("assign-1") == "stale"

    error.assert_called_once()
    experiment.recruiter.execute_early_exit_plan.assert_not_called()


def test_early_exit_route_is_idempotent_after_execution():
    from flask import Flask

    from psynet.experiment import Experiment

    participant = MagicMock(early_exited=True)
    experiment = MagicMock()

    with (
        Flask(__name__).test_request_context(
            "/set_participant_as_early_exited/assign-1",
            method="POST",
            json={"offer_id": "already-executed"},
        ),
        patch.object(
            Experiment,
            "get_participant_from_assignment_id",
            return_value=participant,
        ),
        patch("psynet.experiment.get_experiment", return_value=experiment),
        patch("psynet.experiment.success_response", return_value="ok"),
    ):
        assert Experiment.route_set_participant_as_early_exited("assign-1") == "ok"

    experiment.recruiter.execute_early_exit_plan.assert_not_called()


def test_return_without_payment_plan_skips_payment():
    participant = _participant_for_early_exit()
    participant.failed = False
    plan = _early_exit_test_plan(EarlyExitPath.RETURN_WITHOUT_PAYMENT)
    participant.early_exit_plan = plan.to_dict()

    PsyNetRecruiterMixin().execute_early_exit_plan(MagicMock(), participant, plan)

    participant.fail.assert_called_once_with("early_exit_without_payment")
    participant.early_exit_plan = plan.mark_executed().to_dict()
    decision = PsyNetRecruiterMixin().decide_payment(
        participant, experiment=MagicMock(base_payment=1.0)
    )
    assert decision.status == "returned"
    assert decision.platform_base == 0.0
    assert decision.bonus == 0.0


def test_prolific_unpaid_early_exit_skips_screen_out_code():
    config = make_config()
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock()
    participant.failed = True
    participant.status = "working"
    participant.issued_completion_code_type = None
    participant.early_exited = True
    participant.early_exit_plan = (
        EarlyExitPlan.create(
            context=EarlyExitContext.VOLUNTARY,
            path=EarlyExitPath.RETURN_WITHOUT_PAYMENT,
            confirmation=EarlyExitConfirmation(
                title="Leave?",
                message="No payment.",
                confirm_label="Leave without payment",
                cancel_label="Continue",
            ),
        )
        .mark_executed()
        .to_dict()
    )
    with patch("psynet.recruiters.get_config", return_value=config):
        assert recruiter.completion_status(participant) == "returned"
        assert recruiter.exit_code_type(participant) is None


def test_offered_plan_does_not_reclassify_a_normal_prolific_completion():
    config = make_config()
    recruiter = make_prolific_recruiter(config)
    participant = MagicMock(
        failed=False,
        status="working",
        issued_completion_code_type=None,
        early_exited=False,
        early_exit_plan=_early_exit_test_plan(EarlyExitPath.SCREEN_OUT).to_dict(),
    )

    with patch("psynet.recruiters.get_config", return_value=config):
        assert recruiter.completion_status(participant) == "approved"
        assert recruiter.exit_code_type(participant) is None


def test_lucid_early_exit_terminates_the_panel_session():
    class FakeLucid(BaseLucidRecruiter):
        def __init__(self):
            pass

        def terminate_participant(
            self,
            participant=None,
            assignment_id=None,
            reason=None,
            details=None,
        ):
            self.seen_reason = reason
            return "https://lucid.example/exit"

    recruiter = FakeLucid()
    participant = MagicMock()
    recruiter.execute_early_exit_plan(
        MagicMock(),
        participant,
        _early_exit_test_plan(EarlyExitPath.TERMINATE_PANEL_SESSION),
    )
    assert recruiter.seen_reason == "early_exit"


def test_lucid_plan_execution_propagates_termination_failure_without_commit():
    recruiter = object.__new__(BaseLucidRecruiter)
    recruiter.lucidservice = MagicMock()
    recruiter.lucidservice.terminate_respondent.side_effect = RuntimeError(
        "Lucid unavailable"
    )
    participant = MagicMock(
        assignment_id="rid-1",
        module_state=None,
    )

    with (
        patch("psynet.recruiters.db.session.commit") as commit,
        pytest.raises(RuntimeError, match="Lucid unavailable"),
    ):
        recruiter.execute_early_exit_plan(
            MagicMock(),
            participant,
            _early_exit_test_plan(EarlyExitPath.TERMINATE_PANEL_SESSION),
        )

    commit.assert_not_called()


def test_prolific_treats_a_failed_early_exit_as_screen_out():
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_participant_with_recruiter(config, failed=True)
    with patch("psynet.recruiters.get_config", return_value=config):
        assert recruiter.completion_status(participant) == "screened_out"


@pytest.mark.parametrize(
    "failed,complete,issued,expect_stamped",
    [
        (False, False, None, False),
        (True, True, None, False),
        (True, False, "DEFAULT", False),
        (True, False, PROLIFIC_UNSUCCESSFUL_CODE_TYPE, True),
    ],
)
def test_issue_unsuccessful_completion_code_first_issuance_wins(
    failed, complete, issued, expect_stamped
):
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    recruiter = make_prolific_recruiter(config)
    participant = make_participant_with_recruiter(config, failed=failed)
    participant.complete = complete
    participant.issued_completion_code_type = issued

    with patch("psynet.recruiters.get_config", return_value=config):
        assert (
            recruiter.issue_unsuccessful_completion_code(participant) is expect_stamped
        )
    assert participant.issued_completion_code_type == (
        PROLIFIC_UNSUCCESSFUL_CODE_TYPE if expect_stamped else issued
    )


def test_on_recruiter_submission_complete_stamps_unsuccessful_code_on_submit():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="submitted")
    )
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.issued_completion_code_type == PROLIFIC_UNSUCCESSFUL_CODE_TYPE
    assert participant.status == "screened_out"


def test_recruiter_exit_info_returns_unsuccessful_code_type_for_failed_participant():
    from psynet.experiment import Experiment

    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(Experiment, "commit_payment_state"):
            assert (
                Experiment.recruiter_exit_info(Experiment, participant)
                == PROLIFIC_UNSUCCESSFUL_CODE_TYPE
            )
    assert participant.issued_completion_code_type == PROLIFIC_UNSUCCESSFUL_CODE_TYPE


def test_recruiter_exit_info_returns_none_for_successful_participant():
    from psynet.experiment import Experiment

    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=False)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(Experiment, "commit_payment_state"):
            assert Experiment.recruiter_exit_info(Experiment, participant) is None
    assert participant.issued_completion_code_type == "DEFAULT"


def test_recruiter_exit_info_returns_none_when_payment_disabled():
    from psynet.experiment import Experiment

    config = make_config(prolific_pay_unsuccessful=False)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(Experiment, "commit_payment_state"):
            assert Experiment.recruiter_exit_info(Experiment, participant) is None
    assert participant.issued_completion_code_type == "DEFAULT"


def test_recruiter_exit_info_commits_issued_completion_code():
    from psynet.experiment import Experiment

    config = make_config(prolific_unsuccessful_base_payment=0.50)
    participant = make_participant_with_recruiter(config, failed=True)

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch.object(Experiment, "commit_payment_state") as commit:
            Experiment.recruiter_exit_info(Experiment, participant)

    commit.assert_called_once()
    assert participant.issued_completion_code_type == PROLIFIC_UNSUCCESSFUL_CODE_TYPE


class PaymentHarness:
    from psynet.experiment import Experiment as _Experiment

    base_payment = 1.00
    decide_and_record_payment = _Experiment.decide_and_record_payment
    pay_decided_bonus = _Experiment.pay_decided_bonus
    pay_review_bonus = _Experiment.pay_review_bonus
    dismiss_review_bonus = _Experiment.dismiss_review_bonus
    _record_payment_outcome_success = _Experiment._record_payment_outcome_success
    _notify_payment_outcome_failed = _Experiment._notify_payment_outcome_failed
    on_recruiter_submission_complete = _Experiment.on_recruiter_submission_complete

    def _lock_participant_for_payment(self, participant):
        return participant

    def __init__(self):
        self.recruit_calls = 0
        self.submission_successful_calls = []
        self.notify_calls = []
        self.payment_commits = 0
        self.commit_before_post = []
        self.notifier = SimpleNamespace(notify=self.notify_calls.append)

    def apply_payment_caps(self, participant, bonus):
        return bonus

    def clip_bonus_for_spend_caps(self, participant, bonus, *, record=True):
        payable = round(float(self.apply_payment_caps(participant, bonus)), 2)
        hard_capped = participant.bonus_status == BONUS_STATUS_CAPPED
        return payable, hard_capped

    def commit_payment_state(self):
        self.payment_commits += 1
        self.commit_before_post.append("commit")

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
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    participant.worker_id = "worker-1"
    participant.recruiter.nickname = "prolific"
    participant.recruiter.approve_hit = MagicMock(return_value=True)
    participant.recruiter.reward_bonus = MagicMock()
    participant.recruiter.report_submission_outcome = MagicMock(
        side_effect=lambda participant, amount, reason: (
            True
            if amount < 0.01
            else participant.recruiter.reward_bonus(participant, amount, reason)
        )
    )
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
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.planned_bonus == 2.25
    assert participant.bonus_attempt_detail is None
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
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.planned_bonus == 1.50
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
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
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
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.planned_bonus == 2.25
    participant.recruiter.reward_bonus.assert_called_once()
    assert harness.recruit_calls == 1


def test_on_recruiter_submission_complete_replays_record_without_paying():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="submitted")
    )
    participant.bonus_status = BONUS_STATUS_SUCCESS
    participant.planned_bonus = 2.25
    participant.bonus = 2.25
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.status == "screened_out"
    assert participant.base_payment == 0.25
    assert harness.recruit_calls == 0
    assert harness.submission_successful_calls == []


def test_submission_complete_replay_rerecords_when_issued_code_changes_while_unconfirmed():
    """A replay still re-runs decide/record. If the issued completion code
    changed after a failed first transfer, status and platform base are
    rewritten without a second money POST or a second recruit.
    """
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    participant.issued_completion_code_type = "DEFAULT"
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.status == "approved"
    assert participant.base_payment == 1.00
    assert participant.bonus is None
    assert harness.recruit_calls == 1
    participant.recruiter.reward_bonus.reset_mock()

    participant.status = "submitted"
    participant.failed = True
    participant.issued_completion_code_type = PROLIFIC_UNSUCCESSFUL_CODE_TYPE

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus is None
    assert participant.status == "screened_out"
    assert participant.base_payment == 0.25
    assert harness.recruit_calls == 1
    assert harness.submission_successful_calls == [participant]


def test_on_recruiter_submission_complete_continues_recruiting_when_transfer_fails():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)

    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus is None
    assert participant.status == "approved"
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT
    assert harness.recruit_calls == 1
    assert harness.submission_successful_calls == [participant]
    assert harness.notify_calls


def test_pay_decided_bonus_skips_caps_when_already_settled():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    participant.bonus_status = BONUS_STATUS_SUCCESS
    participant.planned_bonus = 1.50
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
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT
    assert harness.notify_calls
    assert "Participants dashboard" in harness.notify_calls[0]


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
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail is None


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


def test_reward_and_set_bonus_leaves_unsettled_when_transfer_fails():
    config = make_config(prolific_pay_unsuccessful=False)
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=True, status="returned")
    )
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        with patch("psynet.experiment.get_experiment", return_value=harness):
            PsyNetProlificRecruiterMixin.reward_and_set_bonus(participant)

    assert participant.bonus is None
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.planned_bonus == 2.50
    assert PsyNetProlificRecruiterMixin._return_for_bonus_credited(participant) is False


def test_return_for_bonus_credited_when_hard_cap_paid_a_remainder():
    participant = SimpleNamespace(bonus_status=BONUS_STATUS_CAPPED, bonus=0.50)
    assert PsyNetProlificRecruiterMixin._return_for_bonus_credited(participant) is True


def test_return_for_bonus_credited_when_hard_cap_paid_nothing():
    participant = SimpleNamespace(bonus_status=BONUS_STATUS_CAPPED, bonus=None)
    assert PsyNetProlificRecruiterMixin._return_for_bonus_credited(participant) is True


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


def test_check_stale_bonus_override_rejects_check_bonus():
    from psynet.experiment import Experiment

    class ExpWithCheckBonus(Experiment):
        def check_bonus(self, participant):
            return 1.0

    with pytest.raises(RuntimeError, match="check_bonus"):
        ExpWithCheckBonus.check_stale_bonus_override()


class PaymentCapHarness:
    from psynet.experiment import Experiment as _Experiment

    apply_payment_caps = _Experiment.apply_payment_caps
    clip_bonus_for_spend_caps = _Experiment.clip_bonus_for_spend_caps
    pay_decided_bonus = _Experiment.pay_decided_bonus
    pay_review_bonus = _Experiment.pay_review_bonus
    _record_payment_outcome_success = _Experiment._record_payment_outcome_success

    def __init__(self, *, spent=0.0, hard_max=1100.0, max_participant=25.0):
        self.spent = spent
        self.var = SimpleNamespace(
            hard_max_experiment_payment=hard_max,
            max_participant_payment=max_participant,
            hard_max_experiment_payment_email_sent=False,
        )
        self.hard_max_emails = 0
        self.payment_commits = 0

    def amount_spent(self):
        return self.spent

    def bonus_reason(self):
        return "thanks"

    def commit_payment_state(self):
        self.payment_commits += 1

    def _lock_participant_for_payment(self, participant):
        return participant

    def ensure_hard_max_experiment_payment_email_sent(self):
        self.hard_max_emails += 1
        self.var.hard_max_experiment_payment_email_sent = True


def test_apply_payment_caps_clips_bonus_to_remaining_hard_max():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)
    participant = MagicMock(
        id=1, planned_bonus=0.0, bonus_status=BONUS_STATUS_NOT_DUE_YET
    )
    participant.amount_paid.return_value = 1.00

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.50
    assert participant.planned_bonus == 1.00
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
    assert harness.hard_max_emails == 1
    participant.send_email_max_payment_reached.assert_not_called()


def test_apply_payment_caps_pays_nothing_when_hard_max_has_no_room():
    harness = PaymentCapHarness(spent=10.0, hard_max=10.0)
    participant = MagicMock(
        id=1, planned_bonus=0.0, bonus_status=BONUS_STATUS_NOT_DUE_YET
    )

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.0
    assert participant.planned_bonus == 1.00
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
    assert harness.hard_max_emails == 1
    participant.amount_paid.assert_not_called()
    participant.send_email_max_payment_reached.assert_not_called()


def test_apply_payment_caps_does_not_clip_when_bonus_fits_hard_max():
    harness = PaymentCapHarness(spent=8.00, hard_max=10.0)
    participant = MagicMock(id=1, bonus_status=BONUS_STATUS_NOT_DUE_YET)
    participant.amount_paid.return_value = 1.00

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 1.00
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
    assert harness.hard_max_emails == 0


def test_apply_payment_caps_clips_to_max_participant_payment():
    harness = PaymentCapHarness(max_participant=5.00)
    participant = MagicMock(id=1, bonus_status=BONUS_STATUS_NOT_DUE_YET)
    participant.amount_paid.return_value = 4.50

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.50
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
    participant.send_email_max_payment_reached.assert_called_once_with(
        harness, 1.00, 0.50
    )


def test_apply_payment_caps_applies_both_hard_max_and_participant_cap():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0, max_participant=5.20)
    participant = MagicMock(
        id=1, planned_bonus=0.0, bonus_status=BONUS_STATUS_NOT_DUE_YET
    )
    participant.amount_paid.return_value = 5.00

    result = harness.apply_payment_caps(participant, 1.00)

    assert result == 0.20
    assert participant.planned_bonus == 1.00
    assert participant.bonus_status == BONUS_STATUS_NOT_DUE_YET
    participant.send_email_max_payment_reached.assert_called_once_with(
        harness, 1.00, 0.20
    )


def test_amount_spent_sums_recorded_base_and_bonus():
    from psynet.experiment import Experiment

    with patch("psynet.experiment.db") as db:
        db.session.query.return_value.one.return_value = (2.00, 0.50)
        assert Experiment.amount_spent() == 2.50


def test_pay_decided_bonus_pays_remaining_hard_max_as_capped():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)
    participant = MagicMock(
        id=1,
        bonus_status=BONUS_STATUS_NOT_DUE_YET,
        planned_bonus=0.0,
        bonus=None,
    )
    participant.amount_paid.return_value = 1.00
    participant.recruiter.report_submission_outcome = MagicMock(return_value=True)
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.00)

    assert harness.pay_decided_bonus(participant, decision) is True
    participant.recruiter.report_submission_outcome.assert_called_once_with(
        participant, 0.50, "thanks"
    )
    assert participant.planned_bonus == 1.00
    assert participant.bonus == 0.50
    assert participant.bonus_status == BONUS_STATUS_CAPPED


def test_pay_decided_bonus_pays_nothing_when_hard_max_has_no_room():
    harness = PaymentCapHarness(spent=10.0, hard_max=10.0)
    participant = MagicMock(
        id=1,
        bonus_status=BONUS_STATUS_NOT_DUE_YET,
        planned_bonus=0.0,
        bonus=None,
    )
    participant.recruiter.report_submission_outcome = MagicMock(return_value=True)
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.00)

    assert harness.pay_decided_bonus(participant, decision) is True
    participant.recruiter.report_submission_outcome.assert_not_called()
    assert participant.planned_bonus == 1.00
    assert participant.bonus is None
    assert participant.bonus_status == BONUS_STATUS_CAPPED
    assert harness.payment_commits == 0


def test_pay_decided_bonus_settles_subcent_without_claim_for_default_recruiter():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=0.0)

    assert harness.pay_decided_bonus(participant, decision) is True
    participant.recruiter.report_submission_outcome.assert_not_called()
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus is None
    assert participant.planned_bonus == 0.0
    assert harness.payment_commits == 0


def test_pay_decided_bonus_skips_when_already_capped():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    participant.planned_bonus = 1.00
    participant.bonus_status = BONUS_STATUS_CAPPED
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.00)

    assert harness.pay_decided_bonus(participant, decision) is True
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_CAPPED
    assert participant.planned_bonus == 1.00


def test_apply_payment_caps_is_not_latched_after_a_clip():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)
    clipped = MagicMock(id=1, planned_bonus=0.0, bonus_status=BONUS_STATUS_NOT_DUE_YET)
    clipped.amount_paid.return_value = 1.00
    assert harness.apply_payment_caps(clipped, 1.00) == 0.50

    later = MagicMock(id=2, planned_bonus=0.0, bonus_status=BONUS_STATUS_NOT_DUE_YET)
    later.amount_paid.return_value = 1.00
    assert harness.apply_payment_caps(later, 0.40) == 0.40


def test_decide_payment_uses_issued_default_code_even_if_later_failed():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = make_participant_with_recruiter(
        config, failed=True, status="submitted"
    )
    participant.issued_completion_code_type = "DEFAULT"

    decision = decide_for(participant, config)

    assert decision.status == "approved"
    assert decision.platform_base == 1.00


def test_decide_payment_uses_issued_unsuccessful_code_even_if_not_failed():
    config = make_config(prolific_unsuccessful_base_payment=0.25)
    participant = make_participant_with_recruiter(
        config, failed=False, status="submitted"
    )
    participant.issued_completion_code_type = PROLIFIC_UNSUCCESSFUL_CODE_TYPE

    decision = decide_for(participant, config)

    assert decision.status == "screened_out"
    assert decision.platform_base == 0.25


def test_pay_decided_bonus_does_not_repost_when_review_is_needed():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    assert harness.pay_decided_bonus(participant, decision) is False
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT
    assert harness.notify_calls

    assert harness.pay_decided_bonus(participant, decision) is False
    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus is None
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT


def test_pay_decided_bonus_skips_unconfirmed_for_local_recruiter():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    participant.bonus_status = BONUS_STATUS_UNCONFIRMED
    participant.planned_bonus = 1.50
    participant.recruiter.has_external_bonus_payment = MagicMock(return_value=False)
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    assert harness.pay_decided_bonus(participant, decision) is False
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED


def test_pay_decided_bonus_respects_status_after_lock():
    config = make_config()
    original = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    locked = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    locked.bonus_status = BONUS_STATUS_UNCONFIRMED
    locked.planned_bonus = 1.50
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    class LockHarness(PaymentHarness):
        def _lock_participant_for_payment(self, participant):
            return locked

    harness = LockHarness()
    assert harness.pay_decided_bonus(original, decision) is False
    original.recruiter.reward_bonus.assert_not_called()
    locked.recruiter.reward_bonus.assert_not_called()


def test_pay_decided_bonus_commits_unconfirmed_before_post():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="approved")
    )
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.00, bonus=1.50)

    def post(_participant, amount, _reason):
        harness.commit_before_post.append(("post", amount))
        return True

    participant.recruiter.reward_bonus.side_effect = post
    assert harness.pay_decided_bonus(participant, decision) is True
    assert harness.commit_before_post[0] == "commit"
    assert harness.commit_before_post[1] == ("post", 1.50)
    assert harness.payment_commits == 1


def test_on_recruiter_submission_complete_does_not_repost_after_failed_transfer():
    config = make_config()
    participant = prepare_payout_participant(
        make_participant_with_recruiter(config, failed=False, status="submitted")
    )
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()

    with patch("psynet.recruiters.get_config", return_value=config):
        harness.on_recruiter_submission_complete(participant, event=None)
        participant.status = "submitted"
        harness.on_recruiter_submission_complete(participant, event=None)

    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.status == "approved"
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT
    assert harness.recruit_calls == 1


def test_needing_payment_review_filters_flagged_participants():
    flagged = [MagicMock(id=1), MagicMock(id=3)]
    for participant in flagged:
        participant.recruiter.has_external_bonus_payment.return_value = True
    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.all.return_value = flagged

    with patch.object(Participant, "query", query):
        assert Participant.needing_payment_review() == flagged

    query.filter_by.assert_called_once_with(bonus_status=BONUS_STATUS_UNCONFIRMED)


def test_needing_payment_review_skips_hotair_participants():
    hotair = MagicMock(id=1)
    hotair.recruiter.has_external_bonus_payment.return_value = False
    prolific = MagicMock(id=2)
    prolific.recruiter.has_external_bonus_payment.return_value = True
    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.all.return_value = [
        hotair,
        prolific,
    ]

    with patch.object(Participant, "query", query):
        assert Participant.needing_payment_review() == [prolific]


def test_dashboard_participants_includes_review_list():
    from flask import Flask

    from psynet.experiment import Experiment

    needing = [SimpleNamespace(id=7, planned_bonus=1.5)]
    app = Flask("psynet_test")
    with app.test_request_context("/dashboard/participants"):
        with patch(
            "psynet.experiment.Participant.needing_payment_review",
            return_value=needing,
        ):
            with patch(
                "psynet.experiment.render_template", return_value="ok"
            ) as render:
                with patch(
                    "psynet.experiment.get_experiment_url", return_value="http://exp"
                ):
                    with patch("psynet.experiment.get_config") as get_config:
                        get_config.return_value.currency = "$"
                        assert Experiment.dashboard_participants() == "ok"

    kwargs = render.call_args.kwargs
    assert kwargs["participants_needing_review"] is needing
    assert kwargs["title"] == "Participants"
    assert kwargs["currency"] == "$"


def test_bonus_payments_total_converts_pence_to_currency():
    from psynet.recruiters import _bonus_payments_total

    assert _bonus_payments_total([1000, 50]) == 10.50
    assert _bonus_payments_total([]) == 0.0
    assert _bonus_payments_total(None) == 0.0


def _mock_prolific_service():
    service = MagicMock()
    service.api_token = "tok"
    service.api_root = "https://api.prolific.com/api/v1"
    service.referer_header = "https://example.com"
    return service


def test_prolific_apparent_bonus_paid_sums_submission_bonus_payments():
    recruiter = make_prolific_recruiter(make_config())
    recruiter.prolificservice = _mock_prolific_service()
    participant = MagicMock(assignment_id="submission-1")
    response = MagicMock(ok=True, status_code=200)
    response.json.return_value = {
        "bonus_payments": [150, 25],
        "status": "APPROVED",
    }

    with patch("psynet.recruiters.requests.get", return_value=response) as get:
        view = recruiter.platform_payment_view(participant)

    assert view.supported is True
    assert view.bonus == 1.75
    assert view.submission_status == "APPROVED"
    get.assert_called_once()
    assert get.call_args.args[0].endswith("/submissions/submission-1/")
    recruiter.prolificservice._req.assert_not_called()


def _screen_out_platform_view(bonus_payments, config, participant):
    recruiter = make_prolific_recruiter(config)
    recruiter.prolificservice = _mock_prolific_service()
    response = MagicMock(ok=True, status_code=200)
    response.json.return_value = {
        "bonus_payments": bonus_payments,
        "status": "AWAITING REVIEW",
    }
    with patch("psynet.recruiters.get_config", return_value=config):
        with patch("psynet.recruiters.requests.get", return_value=response):
            return recruiter.platform_payment_view(participant)


def test_prolific_platform_view_excludes_screen_out_reward_for_screened_out():
    """Prolific reports the fixed screen-out reward inside ``bonus_payments``
    (live run: [20, 30] = 20p screen-out reward + 30p top-up). The view must
    exclude it so Dashboard Pay does not treat it as PsyNet's top-up and
    underpay a failed bonus.
    """
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    participant = MagicMock(
        assignment_id="submission-1",
        status="screened_out",
        issued_completion_code_type=PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    )

    view = _screen_out_platform_view([20, 30], config, participant)

    assert view.bonus == 0.30


def test_prolific_platform_view_removes_only_one_matching_screen_out_entry():
    # If the top-up equals the fixed reward ([20, 20]), only one entry is
    # treated as the screen-out reward.
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    participant = MagicMock(
        assignment_id="submission-1",
        status="screened_out",
        issued_completion_code_type=PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    )

    view = _screen_out_platform_view([20, 20], config, participant)

    assert view.bonus == 0.20


def test_prolific_platform_view_reports_zero_when_only_screen_out_reward_present():
    # Only the automatic screen-out reward landed; the top-up is still owed,
    # so the apparent PsyNet bonus must be zero.
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    participant = MagicMock(
        assignment_id="submission-1",
        status="screened_out",
        issued_completion_code_type=PROLIFIC_UNSUCCESSFUL_CODE_TYPE,
    )

    view = _screen_out_platform_view([20], config, participant)

    assert view.bonus == 0.0


def test_prolific_platform_view_keeps_full_total_for_non_screened_out():
    config = make_config(prolific_unsuccessful_base_payment=0.20)
    participant = MagicMock(
        assignment_id="submission-1",
        status="approved",
        issued_completion_code_type="DEFAULT",
    )

    view = _screen_out_platform_view([20, 30], config, participant)

    assert view.bonus == 0.50


def test_prolific_apparent_bonus_paid_returns_none_when_lookup_fails():
    recruiter = make_prolific_recruiter(make_config())
    recruiter.prolificservice = _mock_prolific_service()
    participant = MagicMock(assignment_id="submission-1", id=9)
    response = MagicMock(ok=False, status_code=404)

    with patch("psynet.recruiters.requests.get", return_value=response):
        assert recruiter.apparent_bonus_paid(participant) is None
    recruiter.prolificservice._req.assert_not_called()


def test_dashboard_participants_polls_platform_when_opening_a_participant():
    from flask import Flask

    from psynet.experiment import Experiment
    from psynet.recruiters import PlatformPaymentView

    recruiter = MagicMock()
    recruiter.platform_payment_view.return_value = PlatformPaymentView(
        supported=True, bonus=0.75, submission_status="APPROVED"
    )
    participant = SimpleNamespace(id=2, recruiter=recruiter)
    app = Flask("psynet_test")
    with app.test_request_context("/dashboard/participants?participant_id=2"):
        with patch.object(
            Experiment,
            "get_participant_from_participant_id",
            return_value=participant,
        ):
            with patch(
                "psynet.experiment.Participant.needing_payment_review",
                return_value=[],
            ):
                with patch("psynet.experiment.render_template", return_value="ok"):
                    with patch(
                        "psynet.experiment.get_experiment_url",
                        return_value="http://exp",
                    ):
                        with patch("psynet.experiment.get_config") as get_config:
                            get_config.return_value.currency = "$"
                            assert Experiment.dashboard_participants() == "ok"

    recruiter.platform_payment_view.assert_called_once_with(participant)
    assert participant.platform_payment_supported is True
    assert participant.platform_bonus == 0.75
    assert participant.platform_submission_status == "APPROVED"


def test_hotair_apparent_bonus_paid_is_unknown():
    from psynet.recruiters import HotAirRecruiter

    recruiter = object.__new__(HotAirRecruiter)
    assert recruiter.can_report_apparent_bonus() is False
    assert recruiter.has_external_bonus_payment() is False
    assert recruiter.platform_payment_view(MagicMock()).supported is False
    assert recruiter.apparent_bonus_paid(MagicMock()) is None


def test_generic_recruiter_has_no_external_bonus_payment():
    from psynet.recruiters import GenericRecruiter

    recruiter = object.__new__(GenericRecruiter)
    assert recruiter.has_external_bonus_payment() is False


def test_submit_assignment_page_shows_a_spinner():
    from psynet.recruiters import GenericRecruiter

    page = object.__new__(GenericRecruiter).submit_assignment()

    assert "spinner-border" in page.content
    assert page.js_vars["execute_front_end_js"] == "psynet.finishAndGoToExit()"


def _resolve_show_reward(recruiter_cls, configured):
    from psynet.experiment import Experiment

    exp = object.__new__(Experiment)
    # recruiter is a cached_property, so seeding the instance dict is enough.
    exp.__dict__["recruiter"] = object.__new__(recruiter_cls)
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: (
        configured if key == "show_reward" else default
    )
    with patch("psynet.experiment.get_config", return_value=config):
        return exp.show_reward


def test_show_reward_defaults_to_the_recruiter():
    from psynet.recruiters import GenericRecruiter, HotAirRecruiter, ProlificRecruiter

    # Unset in config: recruiters that cannot pay do not quote a reward.
    assert _resolve_show_reward(GenericRecruiter, None) is False
    assert _resolve_show_reward(HotAirRecruiter, None) is False
    assert _resolve_show_reward(ProlificRecruiter, None) is True


def test_explicit_show_reward_config_wins():
    from psynet.recruiters import GenericRecruiter, ProlificRecruiter

    assert _resolve_show_reward(GenericRecruiter, True) is True
    assert _resolve_show_reward(ProlificRecruiter, False) is False


def test_all_recruiter_exit_pages_are_owned_by_psynet():
    """Platform submit pages keep their behavior in PsyNet-themed wrappers."""
    from psynet.recruiters import (
        GenericRecruiter,
        HotAirRecruiter,
        LabRecruiter,
        MTurkRecruiter,
        ProlificRecruiter,
        PsyNetExitPageMixin,
    )

    def owner(cls):
        return next(c for c in cls.__mro__ if "exit_response" in c.__dict__)

    assert owner(HotAirRecruiter) is PsyNetExitPageMixin
    assert owner(LabRecruiter) is PsyNetExitPageMixin
    assert owner(ProlificRecruiter).__name__ == "PsyNetProlificRecruiterMixin"
    assert owner(MTurkRecruiter) is MTurkRecruiter
    # GenericRecruiter checks render_exit_message first, then defers to PsyNet's.
    assert owner(GenericRecruiter) is GenericRecruiter
    assert PsyNetExitPageMixin in GenericRecruiter.__mro__


def test_psynet_exit_page_says_nothing_about_payment():
    import re
    from importlib import resources

    source = (
        resources.files("psynet") / "templates/psynet_exit_recruiter.html"
    ).read_text(encoding="utf-8")
    body = re.sub(r"\{#.*?#\}", "", source, flags=re.DOTALL)

    for term in ("reward", "Bonus", "Base Pay", "currency", "compensation"):
        assert term not in body, f"exit page should not mention {term!r}"


def test_psynet_exit_page_keeps_back_on_the_thank_you_screen():
    """Back from exit must not revive /start for a finished assignment."""
    from importlib import resources

    source = (
        resources.files("psynet") / "templates/psynet_exit_recruiter.html"
    ).read_text(encoding="utf-8")
    assert "history.pushState" in source
    assert "popstate" in source


@pytest.mark.parametrize(
    "recruiter_class_name", ["GenericRecruiter", "HotAirRecruiter", "LabRecruiter"]
)
def test_psynet_exit_page_renders_for_recruiters_without_platform_exit_pages(
    recruiter_class_name,
):
    """Render the final HTML through each recruiter that owns this page."""
    from importlib import resources

    from flask import Flask, render_template
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    from psynet import recruiters

    app = Flask("psynet_exit_page")
    app.jinja_env.globals.update(
        gettext=lambda text: text,
        pgettext=lambda _context, text: text,
    )
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(resources.files("psynet") / "templates")),
            DictLoader(
                {
                    "base/layout.html": (
                        "<!doctype html><html><head>"
                        "{% block stylesheets %}{% endblock %}"
                        "{% block scripts %}{% endblock %}"
                        "</head><body>{% block body %}{% endblock %}</body></html>"
                    )
                }
            ),
        ]
    )
    experiment = MagicMock()
    experiment.psynet_logo = ""
    experiment.logos = []
    experiment.render_exit_message.return_value = "default_exit_message"
    participant = SimpleNamespace(assignment_id="assignment-123")

    def render_exit_template(template_name, **kwargs):
        return render_template(
            template_name,
            experiment=experiment,
            config=SimpleNamespace(color_mode="light"),
            **kwargs,
        )

    recruiter_class = getattr(recruiters, recruiter_class_name)
    recruiter = object.__new__(recruiter_class)
    with app.test_request_context("/recruiter-exit"):
        with patch(
            "psynet.recruiters.render_template_with_translations",
            side_effect=render_exit_template,
        ):
            html = recruiter.exit_response(experiment, participant)

    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "Thank you for taking part." in html
    assert "You have finished. Your responses have been saved." in html
    assert "Reference" in html
    assert "assignment-123" in html
    assert "Bonus" not in html
    assert "Base Pay" not in html


@pytest.mark.parametrize(
    "recruiter_class_name", ["GenericRecruiter", "HotAirRecruiter", "LabRecruiter"]
)
def test_psynet_exit_page_uses_early_leave_copy_when_early_exited(recruiter_class_name):
    """Early leave should not reuse the finished-session thank-you wording."""
    from importlib import resources

    from flask import Flask, render_template
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    from psynet import recruiters

    app = Flask("psynet_exit_page_early")
    app.jinja_env.globals.update(
        gettext=lambda text: text,
        pgettext=lambda _context, text: text,
    )
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(resources.files("psynet") / "templates")),
            DictLoader(
                {
                    "base/layout.html": (
                        "<!doctype html><html><head>"
                        "{% block stylesheets %}{% endblock %}"
                        "{% block scripts %}{% endblock %}"
                        "</head><body>{% block body %}{% endblock %}</body></html>"
                    )
                }
            ),
        ]
    )
    experiment = MagicMock()
    experiment.psynet_logo = ""
    experiment.logos = []
    experiment.render_exit_message.return_value = "default_exit_message"
    participant = SimpleNamespace(assignment_id="assignment-123", early_exited=True)

    def render_exit_template(template_name, **kwargs):
        return render_template(
            template_name,
            experiment=experiment,
            config=SimpleNamespace(color_mode="light"),
            **kwargs,
        )

    recruiter_class = getattr(recruiters, recruiter_class_name)
    recruiter = object.__new__(recruiter_class)
    with app.test_request_context("/recruiter-exit"):
        with patch(
            "psynet.recruiters.render_template_with_translations",
            side_effect=render_exit_template,
        ):
            html = recruiter.exit_response(experiment, participant)

    assert "You left early. Your responses have been saved." in html
    assert "You have finished." not in html


@pytest.mark.parametrize(
    ("template_name", "context", "expected"),
    [
        (
            "psynet_exit_recruiter_prolific.html",
            {
                "assignment_id": "assignment-123",
                "participant_id": 7,
                "external_submit_url": "https://app.prolific.com/complete",
            },
            (
                "Submit your Prolific study",
                "/prolific-submission-listener",
                "https://app.prolific.com/complete",
            ),
        ),
        (
            "psynet_exit_recruiter_mturk.html",
            {
                "assignment_id": "assignment-123",
                "hit_id": "hit-456",
                "worker_id": "worker-789",
                "external_submit_url": "https://workersandbox.mturk.com/submit",
            },
            (
                "Submit your MTurk HIT",
                'name="assignmentId"',
                "https://workersandbox.mturk.com/submit",
            ),
        ),
    ],
)
def test_platform_exit_pages_render_with_psynet_layout(
    template_name, context, expected
):
    """Platform submit controls retain their fields inside the shared theme."""
    from importlib import resources

    from flask import Flask, render_template
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    app = Flask("psynet_platform_exit")
    app.jinja_env.globals.update(
        gettext=lambda text: text,
        pgettext=lambda _context, text: text,
    )
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(resources.files("psynet") / "templates")),
            DictLoader(
                {
                    "base/layout.html": (
                        "<!doctype html><html><head>"
                        "{% block head %}{% endblock %}"
                        "{% block stylesheets %}{% endblock %}"
                        "</head><body>{% block body %}{% endblock %}"
                        "{% block scripts %}{% endblock %}</body></html>"
                    )
                }
            ),
        ]
    )
    experiment = MagicMock(psynet_logo="", logos=[])
    participant = SimpleNamespace(
        id=7,
        assignment_id="assignment-123",
        hit_id="hit-456",
        unique_id="worker-789:assignment-123",
        worker_id="worker-789",
    )

    with app.test_request_context("/recruiter-exit"):
        html = render_template(
            template_name,
            experiment=experiment,
            participant=participant,
            config=SimpleNamespace(color_mode="light"),
            **context,
        )

    assert '<meta name="viewport"' in html
    assert "css/participant.css" in html
    assert "scripts/psynet.layout.js" in html
    for text in expected:
        assert text in html


def test_prolific_exit_response_selects_psynet_template():
    participant = SimpleNamespace(id=7, assignment_id="assignment-123")
    experiment = MagicMock()
    experiment.recruiter_exit_info.return_value = None
    recruiter = object.__new__(ProlificRecruiter)

    with (
        patch.object(
            ProlificRecruiter,
            "external_submission_url",
            return_value="https://app.prolific.com/complete",
        ),
        patch(
            "psynet.recruiters.render_template_with_translations",
            return_value="html",
        ) as render,
    ):
        assert recruiter.exit_response(experiment, participant) == "html"

    assert render.call_args.args == ("psynet_exit_recruiter_prolific.html",)
    assert render.call_args.kwargs["participant"] is participant
    assert render.call_args.kwargs["external_submit_url"].startswith(
        "https://app.prolific.com/"
    )


def test_mturk_exit_response_selects_psynet_template():
    from psynet.recruiters import MTurkRecruiter

    participant = SimpleNamespace(
        id=7,
        assignment_id="assignment-123",
        hit_id="hit-456",
        worker_id="worker-789",
    )
    recruiter = object.__new__(MTurkRecruiter)

    with (
        patch.object(
            MTurkRecruiter,
            "external_submission_url",
            new_callable=PropertyMock,
            return_value="https://workersandbox.mturk.com/submit",
        ),
        patch(
            "psynet.recruiters.render_template_with_translations",
            return_value="html",
        ) as render,
    ):
        assert recruiter.exit_response(MagicMock(), participant) == "html"

    assert render.call_args.args == ("psynet_exit_recruiter_mturk.html",)
    assert render.call_args.kwargs["participant"] is participant
    assert render.call_args.kwargs["assignment_id"] == "assignment-123"


def _review_participant(apparent=0.0, planned=1.50):
    participant = prepare_payout_participant(
        make_participant_with_recruiter(make_config(), failed=False, status="approved")
    )
    participant.bonus_status = BONUS_STATUS_UNCONFIRMED
    participant.planned_bonus = planned
    participant.recruiter.can_report_apparent_bonus = MagicMock(return_value=True)
    participant.recruiter.apparent_bonus_paid = MagicMock(return_value=apparent)
    return participant


def test_pay_review_bonus_posts_when_platform_shows_zero():
    participant = _review_participant(apparent=0.0)
    participant.recruiter.reward_bonus.return_value = True
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.recruiter.reward_bonus.call_args.args[1] == 1.50
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus == 1.50
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail is None


def test_pay_review_bonus_does_not_post_when_platform_already_paid():
    participant = _review_participant(apparent=1.50)
    participant.recruiter.reward_bonus = MagicMock()
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus == 1.50
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail is None


def test_pay_review_bonus_refuses_when_not_in_review():
    participant = _review_participant()
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "warning"
    participant.recruiter.reward_bonus.assert_not_called()
    assert "not" in message.lower()


def test_pay_review_bonus_refuses_when_lookup_fails():
    participant = _review_participant(apparent=None)
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "warning"
    participant.recruiter.reward_bonus.assert_not_called()


def test_pay_review_bonus_posts_when_recruiter_cannot_report():
    participant = _review_participant(apparent=None)
    participant.recruiter.can_report_apparent_bonus = MagicMock(return_value=False)
    participant.recruiter.reward_bonus.return_value = True
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.planned_bonus == 1.50
    assert participant.bonus == 1.50
    assert participant.bonus_attempt_detail is None


def test_pay_review_bonus_leaves_review_when_post_fails():
    participant = _review_participant(apparent=0.0)
    participant.recruiter.reward_bonus.return_value = False
    harness = PaymentHarness()

    category, message = harness.pay_review_bonus(participant)

    assert category == "danger"
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus is None
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT


def test_pay_review_bonus_refuses_overlapping_pay():
    participant = _review_participant(apparent=0.0)
    harness = PaymentHarness()
    nested = []

    def post(_participant, amount, _reason):
        nested.append(harness.pay_review_bonus(_participant))
        return True

    participant.recruiter.reward_bonus.side_effect = post
    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    assert nested == [
        (
            "warning",
            f"A bonus payment is already in progress for participant {participant.id}.",
        )
    ]
    participant.recruiter.reward_bonus.assert_called_once()
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert harness.payment_commits == 0


def test_pay_review_bonus_can_retry_after_failed_post():
    participant = _review_participant(apparent=0.0)
    harness = PaymentHarness()
    participant.recruiter.reward_bonus.return_value = False

    category, message = harness.pay_review_bonus(participant)

    assert category == "danger"
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus_attempt_detail == NO_BONUS_ATTEMPT_RESULT

    participant.recruiter.reward_bonus.return_value = True
    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    assert participant.recruiter.reward_bonus.call_count == 2
    assert participant.bonus_status == BONUS_STATUS_SUCCESS


def test_pay_review_bonus_posts_remainder_after_hard_cap_clip():
    participant = _review_participant(apparent=0.0, planned=1.00)
    participant.amount_paid.return_value = 1.00
    participant.recruiter.reward_bonus.return_value = True
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_called_once_with(
        participant, 0.50, "thanks"
    )
    assert participant.bonus_status == BONUS_STATUS_CAPPED
    assert participant.bonus == 0.50
    assert participant.planned_bonus == 1.00
    assert harness.payment_commits == 0
    assert "0.50" in message


def test_pay_review_bonus_records_partial_platform_amount_without_overpaying():
    participant = _review_participant(apparent=0.50, planned=1.00)
    participant.amount_paid.return_value = 1.00
    participant.recruiter.reward_bonus = MagicMock()
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_CAPPED
    assert participant.bonus == 0.50
    assert participant.planned_bonus == 1.00


def test_pay_review_bonus_does_not_record_apparent_above_payable():
    participant = _review_participant(apparent=2.00, planned=1.00)
    participant.amount_paid.return_value = 1.00
    participant.recruiter.reward_bonus = MagicMock()
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)

    category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    participant.recruiter.reward_bonus.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_CAPPED
    assert participant.bonus == 0.50
    assert participant.planned_bonus == 1.00


def test_clip_bonus_for_spend_caps_record_false_does_not_settle():
    harness = PaymentCapHarness(spent=9.50, hard_max=10.0)
    participant = MagicMock(
        id=1, planned_bonus=1.00, bonus_status=BONUS_STATUS_UNCONFIRMED
    )
    participant.amount_paid.return_value = 1.00

    payable, hard_capped = harness.clip_bonus_for_spend_caps(
        participant, 1.00, record=False
    )

    assert payable == 0.50
    assert hard_capped is True
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert harness.hard_max_emails == 0


def test_dismiss_review_bonus_clears_review_without_posting():
    participant = _review_participant(apparent=0.0)
    participant.bonus_attempt_detail = "timeout"
    participant.recruiter.reward_bonus = MagicMock()
    harness = PaymentHarness()

    category, message = harness.dismiss_review_bonus(participant)

    assert category == "success"
    assert participant.bonus_status == BONUS_STATUS_DISMISSED
    assert participant.bonus is None
    assert participant.planned_bonus == 1.50
    assert participant.bonus_attempt_detail == "timeout"
    participant.recruiter.reward_bonus.assert_not_called()
    assert "without posting" in message.lower()


@pytest.mark.parametrize(
    "status, label",
    [
        (BONUS_STATUS_UNCONFIRMED, "Unconfirmed"),
        (BONUS_STATUS_SUCCESS, "Success"),
        (BONUS_STATUS_DISMISSED, "Dismissed"),
        (BONUS_STATUS_CAPPED, "Capped"),
        (BONUS_STATUS_NOT_DUE_YET, "Not due yet"),
        (None, "Not due yet"),
        ("unknown", "Not due yet"),
    ],
)
def test_display_bonus_status(status, label):
    assert display_bonus_status(SimpleNamespace(bonus_status=status)) == label


def test_bonus_status_helpers():
    unconfirmed = SimpleNamespace(bonus_status=BONUS_STATUS_UNCONFIRMED)
    assert bonus_needs_review(unconfirmed)
    assert not bonus_is_settled(unconfirmed)
    assert not bonus_needs_review(
        SimpleNamespace(
            bonus_status=BONUS_STATUS_UNCONFIRMED,
            recruiter=SimpleNamespace(has_external_bonus_payment=lambda: False),
        )
    )
    assert bonus_is_settled(SimpleNamespace(bonus_status=BONUS_STATUS_SUCCESS))
    assert bonus_is_settled(SimpleNamespace(bonus_status=BONUS_STATUS_DISMISSED))
    assert bonus_is_settled(SimpleNamespace(bonus_status=BONUS_STATUS_CAPPED))
    assert not bonus_needs_review(SimpleNamespace(bonus_status=BONUS_STATUS_SUCCESS))
    assert bonus_transfer_already_claimed(
        SimpleNamespace(bonus_status=BONUS_STATUS_UNCONFIRMED)
    )
    assert bonus_transfer_already_claimed(
        SimpleNamespace(bonus_status=BONUS_STATUS_SUCCESS)
    )
    assert review_bonus_pay_in_progress(
        SimpleNamespace(bonus_attempt_detail=BONUS_PAY_IN_PROGRESS)
    )
    assert not review_bonus_pay_in_progress(
        SimpleNamespace(bonus_attempt_detail=NO_BONUS_ATTEMPT_RESULT)
    )
    assert not bonus_transfer_already_claimed(
        SimpleNamespace(bonus_status=BONUS_STATUS_NOT_DUE_YET)
    )


def test_dismiss_review_bonus_refuses_when_not_in_review():
    participant = _review_participant()
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    harness = PaymentHarness()

    category, message = harness.dismiss_review_bonus(participant)

    assert category == "warning"
    participant.recruiter.reward_bonus.assert_not_called()


def test_prolific_reward_bonus_returns_false_on_exception():
    recruiter = make_prolific_recruiter(make_config())
    recruiter.prolificservice = MagicMock()
    recruiter.prolificservice.pay_session_bonus.side_effect = ProlificServiceException(
        "no"
    )
    participant = MagicMock(worker_id="w")
    with patch.object(
        type(recruiter), "current_study_id", PropertyMock(return_value="study-1")
    ):
        with patch("psynet.recruiters.handle_recruitment_error") as handle:
            assert recruiter.reward_bonus(participant, 1.0, "r") is False
            handle.assert_called_once()
            assert participant.bonus_attempt_detail == "no"


def test_mturk_reward_bonus_returns_false_when_grant_bonus_returns_false():
    from psynet.recruiters import MTurkRecruiter

    recruiter = object.__new__(MTurkRecruiter)
    recruiter.mturkservice = MagicMock()
    recruiter.mturkservice.grant_bonus.return_value = False
    participant = MagicMock(assignment_id="a")
    with patch("psynet.recruiters.handle_recruitment_error") as handle:
        assert recruiter.reward_bonus(participant, 1.0, "r") is False
        handle.assert_called_once()
        assert "assignment a" in participant.bonus_attempt_detail


def test_hotair_reward_bonus_returns_true():
    from psynet.recruiters import HotAirRecruiter

    recruiter = object.__new__(HotAirRecruiter)
    assert recruiter.reward_bonus(MagicMock(assignment_id="a"), 1.0, "thanks") is True


def test_lucid_reward_bonus_terminates_when_responses_empty():
    from psynet.recruiters import BaseLucidRecruiter

    recruiter = object.__new__(BaseLucidRecruiter)
    recruiter.complete_participant = MagicMock()
    recruiter.terminate_participant = MagicMock()
    participant = MagicMock(progress=0.5, id=1)

    with patch("psynet.recruiters.Response") as response_cls:
        response_cls.query.filter_by.return_value.order_by.return_value.all.return_value = []
        assert recruiter.reward_bonus(participant, 0.0, "thanks") is True

    recruiter.complete_participant.assert_not_called()
    recruiter.terminate_participant.assert_called_once_with(
        participant=participant, reason="participant-did-not-complete"
    )


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


def test_calculate_reward_treats_missing_time_fields_as_zero():
    class RewardParticipant:
        time_credit = None
        performance_reward = None
        time_reward = Participant.time_reward
        calculate_reward = Participant.calculate_reward

    with patch("psynet.participant.get_config") as get_config:
        get_config.return_value.get.return_value = 9.0
        assert RewardParticipant().calculate_reward() == 0.0


def make_lab_recruiter(token="abc123", base_payment=1.5, mode=None):
    recruiter = BaseLabRecruiter.__new__(BaseLabRecruiter)
    recruiter.config = {
        "lab_recruiter_auth_token": token,
        "base_payment": base_payment,
    }
    if mode is not None:
        recruiter.config["mode"] = mode
    recruiter.external_submission_url = "https://recruiter.example.edu/tasks"
    return recruiter


def make_lab_participant(failed=False):
    participant = MagicMock()
    participant.assignment_id = "assignment-1"
    participant.failed = failed
    participant.failure_tags = ["too_slow"] if failed else []
    participant.bonus = None
    participant.bonus_attempt_detail = None
    return participant


@pytest.mark.parametrize(
    "failed, url_suffix, failed_reason",
    [
        (False, "/complete", []),
        (True, "/fail", ["too_slow"]),
    ],
)
def test_lab_recruiter_report_submission_outcome_posts(
    failed, url_suffix, failed_reason
):
    recruiter = make_lab_recruiter(token="secret-key")
    participant = make_lab_participant(failed=failed)

    with patch("psynet.recruiters.requests.post") as post:
        posted = recruiter.report_submission_outcome(
            participant, amount=0.25, reason="completed"
        )

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


def test_lab_recruiter_report_submission_outcome_skips_post_when_token_missing(caplog):
    recruiter = make_lab_recruiter(token="")
    participant = make_lab_participant()

    with (
        patch("psynet.recruiters.requests.post") as post,
        caplog.at_level("ERROR", logger="psynet"),
    ):
        posted = recruiter.report_submission_outcome(
            participant, amount=0.25, reason="completed"
        )

    post.assert_not_called()
    assert "lab_recruiter_auth_token is not set" in caplog.text
    assert not posted
    assert participant.bonus_attempt_detail == "lab_recruiter_auth_token is not set."


def test_lab_recruiter_debug_without_token_skips_post_as_success(caplog):
    recruiter = make_lab_recruiter(token="", mode="debug")
    participant = make_lab_participant()

    with (
        patch("psynet.recruiters.requests.post") as post,
        caplog.at_level("INFO", logger="psynet"),
    ):
        posted = recruiter.report_submission_outcome(
            participant, amount=0.0, reason="completed"
        )

    post.assert_not_called()
    assert posted is True
    assert "Skipping lab-recruiter completion POST in debug" in caplog.text
    assert participant.bonus_attempt_detail is None


def test_lab_recruiter_token_prefix_is_normalized():
    recruiter = make_lab_recruiter(token="Token config-secret")
    participant = make_lab_participant()

    with patch("psynet.recruiters.requests.post") as post:
        recruiter.report_submission_outcome(
            participant, amount=0.25, reason="completed"
        )

    assert post.call_args.kwargs["headers"] == {"Authorization": "Token config-secret"}


def test_lab_recruiter_report_submission_outcome_logs_http_error(caplog):
    from requests import HTTPError

    recruiter = make_lab_recruiter()
    participant = make_lab_participant()

    with (
        patch("psynet.recruiters.requests.post") as post,
        caplog.at_level("ERROR", logger="psynet"),
    ):
        post.return_value.raise_for_status.side_effect = HTTPError("bad response")
        posted = recruiter.report_submission_outcome(
            participant, amount=0.25, reason="completed"
        )

    assert not posted
    assert "Lab Recruiter completion POST" in caplog.text
    assert participant.bonus is None


def test_lab_recruiter_reward_bonus_raises():
    recruiter = make_lab_recruiter()
    participant = make_lab_participant()

    with pytest.raises(RuntimeError, match="report_submission_outcome"):
        recruiter.reward_bonus(participant, 0.25, "completed")


def test_lab_recruiter_validate_config_requires_token_outside_debug():
    make_lab_recruiter(token="abc123").validate_config(mode="live")
    with pytest.raises(ValueError, match="lab_recruiter_auth_token must be set"):
        make_lab_recruiter(token="").validate_config(mode="live")
    make_lab_recruiter(token="").validate_config(mode="debug")


@pytest.mark.parametrize(
    "amount, delivered",
    [
        (0.0, None),
        (0.25, 0.25),
    ],
)
def test_payment_pipeline_reports_lab_outcome_once(amount, delivered):
    participant = make_lab_participant()
    participant.id = 9
    participant.recruiter = make_lab_recruiter()
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.50, bonus=amount)

    with patch("psynet.recruiters.requests.post") as post:
        assert harness.pay_decided_bonus(participant, decision)
        assert harness.pay_decided_bonus(participant, decision)

    post.assert_called_once()
    assert post.call_args.kwargs["json"]["bonus"] == amount
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus == delivered
    assert harness.payment_commits == 1


def test_pay_decided_bonus_debug_lab_without_token_settles():
    participant = make_lab_participant()
    participant.id = 9
    participant.recruiter = make_lab_recruiter(token="", mode="debug")
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.50, bonus=0.0)

    with patch("psynet.recruiters.requests.post") as post:
        assert harness.pay_decided_bonus(participant, decision) is True

    post.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus is None
    assert not harness.notify_calls


def test_pay_decided_bonus_live_lab_without_token_needs_review():
    participant = make_lab_participant()
    participant.id = 9
    participant.recruiter = make_lab_recruiter(token="", mode="live")
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.50, bonus=0.0)

    with patch("psynet.recruiters.requests.post") as post:
        assert harness.pay_decided_bonus(participant, decision) is False

    post.assert_not_called()
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus_attempt_detail == "lab_recruiter_auth_token is not set."
    assert harness.notify_calls


def test_pay_review_bonus_posts_zero_lab_outcome():
    participant = make_lab_participant()
    participant.id = 9
    participant.recruiter = make_lab_recruiter()
    participant.bonus_status = BONUS_STATUS_UNCONFIRMED
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = NO_BONUS_ATTEMPT_RESULT
    harness = PaymentHarness()

    with patch("psynet.recruiters.requests.post") as post:
        category, message = harness.pay_review_bonus(participant)

    assert category == "success"
    post.assert_called_once()
    assert post.call_args.kwargs["json"]["bonus"] == 0.0
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert participant.bonus is None


def test_zero_lab_outcome_failure_stays_unconfirmed():
    from requests import HTTPError

    participant = make_lab_participant()
    participant.id = 9
    participant.recruiter = make_lab_recruiter()
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    harness = PaymentHarness()
    decision = PaymentDecision(status="approved", platform_base=1.50, bonus=0.0)

    with patch("psynet.recruiters.requests.post") as post:
        post.return_value.raise_for_status.side_effect = HTTPError("bad response")
        assert not harness.pay_decided_bonus(participant, decision)

    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert participant.bonus is None
    assert harness.payment_commits == 1


def test_default_outcome_report_skips_zero_and_transfers_real_bonus():
    recruiter = MagicMock()
    recruiter.reward_bonus.return_value = True

    assert PsyNetRecruiterMixin.report_submission_outcome(
        recruiter, MagicMock(), 0.0, "Thanks"
    )
    recruiter.reward_bonus.assert_not_called()

    participant = MagicMock()
    assert PsyNetRecruiterMixin.report_submission_outcome(
        recruiter, participant, 0.25, "Thanks"
    )
    recruiter.reward_bonus.assert_called_once_with(participant, 0.25, "Thanks")


def test_lab_recruiter_consent_rejection_reports_zero_outcome_once():
    recruiter = make_lab_recruiter()
    participant = make_lab_participant(failed=True)
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    experiment = PaymentHarness()

    with patch.object(
        recruiter, "report_submission_outcome", return_value=True
    ) as report:
        recruiter.after_rejected_consent(experiment, participant)
        recruiter.after_rejected_consent(experiment, participant)

    report.assert_called_once_with(participant, 0.0, "thanks")
    assert participant.bonus_status == BONUS_STATUS_SUCCESS
    assert experiment.payment_commits == 2
    assert not experiment.notify_calls


def test_lab_recruiter_consent_rejection_failure_stays_unconfirmed():
    recruiter = make_lab_recruiter()
    participant = make_lab_participant(failed=True)
    participant.bonus_status = BONUS_STATUS_NOT_DUE_YET
    participant.planned_bonus = 0.0
    participant.bonus_attempt_detail = None
    experiment = PaymentHarness()

    with patch.object(
        recruiter, "report_submission_outcome", return_value=False
    ) as report:
        recruiter.after_rejected_consent(experiment, participant)
        recruiter.after_rejected_consent(experiment, participant)

    report.assert_called_once_with(participant, 0.0, "thanks")
    assert participant.bonus_status == BONUS_STATUS_UNCONFIRMED
    assert experiment.payment_commits == 1
    assert not experiment.notify_calls


def test_rejected_consent_dispatches_recruiter_hook():
    from psynet.end import RejectedConsentLogic

    recruiter = make_lab_recruiter()
    recruiter.after_rejected_consent = MagicMock()
    experiment = MagicMock()
    experiment.recruiter = recruiter
    experiment.with_lucid_recruitment.return_value = False
    participant = MagicMock()
    participant.recruiter = recruiter

    RejectedConsentLogic().before_debrief(experiment, participant)

    participant.fail.assert_called_once_with()
    recruiter.after_rejected_consent.assert_called_once_with(experiment, participant)
