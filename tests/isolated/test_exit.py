from types import SimpleNamespace

import pytest

from psynet.exit import (
    EarlyExitConfirmation,
    ErrorRecoveryPresentation,
    ExitContext,
    ExitPath,
    ExitPlan,
    PaymentDecision,
    _committed_exit_plan,
)


def _payment():
    return PaymentDecision(status="screened_out", platform_base=0.25, bonus=0.55)


def _plan(context=ExitContext.VOLUNTARY):
    return ExitPlan.create(
        context=context,
        path=ExitPath.SCREEN_OUT,
        payment=_payment(),
        currency="£",
        confirmation=EarlyExitConfirmation(
            title="Leave?",
            message="Your work is saved.",
            confirm_label="Leave",
            cancel_label="Continue",
        ),
    )


def test_exit_plan_round_trips_through_participant_column_data():
    plan = _plan()

    restored = ExitPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert restored.to_dict()["path"] == "screen_out"
    assert restored.to_dict()["payment"] == {
        "status": "screened_out",
        "platform_base": 0.25,
        "bonus": 0.55,
    }
    assert restored.to_dict()["confirmation"]["message"] == "Your work is saved."


@pytest.mark.parametrize("context", list(ExitContext))
def test_exit_plan_supports_every_terminal_context(context):
    plan = _plan(context)

    assert ExitPlan.from_dict(plan.to_dict()).context is context


def test_exit_plan_refuses_stored_data_it_cannot_read():
    with pytest.raises(ValueError, match="status"):
        ExitPlan.from_dict({**_plan().to_dict(), "status": "half-done"})


def test_committed_exit_plan_is_the_terminal_source_of_truth():
    plan = _plan()
    participant = SimpleNamespace(exit_plan=plan.to_dict())
    assert _committed_exit_plan(participant) is None

    committed = plan.mark_committed()
    participant.exit_plan = committed.to_dict()
    assert _committed_exit_plan(participant) == committed


def test_exit_plan_can_record_a_partial_payment_decision_for_error_recovery():
    plan = ExitPlan.create(
        context=ExitContext.ERROR_RECOVERY,
        path=ExitPath.SCREEN_OUT,
        payment=PaymentDecision(
            status="screened_out",
            platform_base=0.25,
            bonus=0.0,
        ),
        payment_is_final=False,
        currency="$",
    )

    restored = ExitPlan.from_dict(plan.to_dict())

    assert restored.payment == PaymentDecision(
        status="screened_out",
        platform_base=0.25,
        bonus=0.0,
    )
    assert restored.payment_is_final is False


def test_error_recovery_presentation_rejects_an_incomplete_handoff():
    with pytest.raises(ValueError, match="button label"):
        ErrorRecoveryPresentation(
            message="Continue.",
            failure_message="Try again.",
            destination_url="https://example.test/exit",
        )
