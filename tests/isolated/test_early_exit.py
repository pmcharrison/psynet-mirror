from types import SimpleNamespace

import pytest

from psynet.early_exit import (
    EarlyExitConfirmation,
    EarlyExitContext,
    EarlyExitPath,
    EarlyExitPlan,
    ErrorRecoveryPresentation,
    _executed_early_exit_plan,
)


def _plan():
    return EarlyExitPlan.create(
        context=EarlyExitContext.VOLUNTARY,
        path=EarlyExitPath.SCREEN_OUT,
        confirmation=EarlyExitConfirmation(
            title="Leave?",
            message="Your work is saved.",
            confirm_label="Leave",
            cancel_label="Continue",
        ),
        quoted_amounts={"currency": "£", "fixed_minor": 20},
    )


def test_early_exit_plan_round_trips_through_participant_column_data():
    plan = _plan()

    restored = EarlyExitPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert restored.to_dict()["path"] == "screen_out"
    assert restored.to_dict()["confirmation"]["message"] == "Your work is saved."


def test_early_exit_plan_refuses_stored_data_it_cannot_read():
    with pytest.raises(ValueError, match="status"):
        EarlyExitPlan.from_dict({**_plan().to_dict(), "status": "half-done"})


def test_only_an_executed_plan_for_an_early_exited_participant_is_current():
    plan = _plan()
    participant = SimpleNamespace(
        early_exit_plan=plan.to_dict(),
        early_exited=True,
    )
    assert _executed_early_exit_plan(participant) is None

    executed = plan.mark_executed()
    participant.early_exit_plan = executed.to_dict()
    assert _executed_early_exit_plan(participant) == executed


def test_error_recovery_presentation_rejects_an_incomplete_handoff():
    with pytest.raises(ValueError, match="button label"):
        ErrorRecoveryPresentation(
            message="Continue.",
            failure_message="Try again.",
            destination_url="https://example.test/exit",
        )


def test_recruiters_keeps_the_previous_domain_type_imports():
    """Existing experiment imports continue to work after the module split."""
    from psynet import recruiters

    assert recruiters.EarlyExitPlan is EarlyExitPlan
    assert recruiters.ErrorRecoveryPresentation is ErrorRecoveryPresentation
