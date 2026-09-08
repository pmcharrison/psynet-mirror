"""Focused contracts for tracked fatal recovery and completion backstops."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dallinger import db
from flask import Flask

from psynet.end import ErrorRecoveryPage, SuccessfulEndLogic
from psynet.exit import ExitContext, ExitPath, ExitPlan, ExitPlanStatus, PaymentDecision
from psynet.experiment import Experiment, get_experiment
from psynet.page import ExecuteFrontEndJS, InfoPage
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment

pytestmark = [
    pytest.mark.parametrize(
        "experiment_directory",
        [path_to_test_experiment("timeline")],
        indirect=True,
    ),
    pytest.mark.usefixtures("in_experiment_directory"),
]


def _make_participant(**overrides):
    experiment = get_experiment()
    participant = Participant(
        experiment=experiment,
        recruiter_id="hotair",
        worker_id=str(uuid.uuid4()),
        hit_id=str(uuid.uuid4()),
        assignment_id=str(uuid.uuid4()),
        mode="debug",
    )
    for key, value in overrides.items():
        setattr(participant, key, value)
    db.session.add(participant)
    db.session.commit()
    return participant


def test_error_page_with_participant_id_does_not_mutate_arbitrary_participant(
    db_session,
):
    """GET /error-page?participant_id=N must not fail strangers."""
    victim = _make_participant()
    victim_id = victim.id
    assert victim.failed is False
    assert victim.exit_plan is None

    with (
        Flask(__name__).test_request_context(f"/error-page?participant_id={victim_id}"),
        patch("psynet.experiment.get_experiment", return_value=get_experiment()),
        patch(
            "psynet.experiment.render_template_with_translations",
            return_value="error page",
        ),
    ):
        Experiment.render_error()

    db.session.remove()
    reloaded = Participant.query.get(victim_id)
    assert reloaded.failed is False
    assert reloaded.exit_plan is None


def test_fatal_response_prepares_recovery_in_the_same_request(db_session):
    """Fatal /response cleanup must not wait for a later browser GET."""
    participant = _make_participant(page_uuid="page-1")
    participant_id = participant.id

    event = MagicMock()
    event.process_response.side_effect = ValueError("boom")
    experiment = get_experiment()
    original_get_current_elt = experiment.timeline.get_current_elt
    seen_current_elt = {"n": 0}

    def failing_page_then_real_timeline(*args, **kwargs):
        if seen_current_elt["n"] == 0:
            seen_current_elt["n"] += 1
            return event
        return original_get_current_elt(*args, **kwargs)

    with (
        patch.object(
            experiment,
            "_participant_request_query",
            return_value=SimpleNamespace(
                with_for_update=lambda **kwargs: SimpleNamespace(
                    populate_existing=lambda: SimpleNamespace(
                        get=lambda _id: participant
                    )
                )
            ),
        ),
        patch.object(
            experiment.timeline,
            "get_current_elt",
            side_effect=failing_page_then_real_timeline,
        ),
        patch.object(Experiment, "report_error"),
        patch(
            "psynet.experiment.error_response", return_value="json error"
        ) as error_response,
    ):
        result = experiment.process_response(
            participant_id=participant_id,
            raw_answer="answer",
            blobs={},
            metadata={},
            page_uuid="page-1",
            client_ip_address="127.0.0.1",
        )

    assert result == "json error"
    error_response.assert_called_once()

    db.session.commit()
    db.session.remove()
    after_fatal = Participant.query.get(participant_id)
    assert after_fatal.failed is True
    assert after_fatal.exit_plan is not None
    assert after_fatal.early_exited is True
    assert ExitPlan.from_dict(after_fatal.exit_plan).status is ExitPlanStatus.COMMITTED
    assert "error_recovery" in (after_fatal.failure_tags or [])
    assert "ValueError" in (after_fatal.failure_tags or [])


def test_generic_tracked_recovery_commits_without_a_recovery_page(db_session):
    """Generic fatal recovery skips error chrome and hands off to recruiter exit."""
    participant = _make_participant(page_uuid="page-1")
    participant_id = participant.id
    experiment = get_experiment()
    Experiment._prepare_error_recovery_plan(
        experiment,
        experiment.recruiter,
        participant,
    )
    db.session.commit()
    unique_id = participant.unique_id

    assert experiment.timeline.get_participant_branch(participant) == (
        "early_exit_release"
    )
    assert not isinstance(
        experiment.timeline.get_current_elt(experiment, participant),
        ErrorRecoveryPage,
    )
    assert isinstance(
        experiment.timeline.get_current_elt(experiment, participant),
        ExecuteFrontEndJS,
    )
    plan = ExitPlan.from_dict(participant.exit_plan)
    assert plan.status is ExitPlanStatus.COMMITTED
    assert participant.early_exited is True

    with (
        Flask(__name__).test_request_context(
            f"/timeline?unique_id={unique_id}",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ),
        patch.object(experiment, "participant_task_completed"),
        patch("dallinger.experiment_server.worker_events.worker_function"),
    ):
        response = Experiment._route_timeline(experiment, participant, mode=None)

    assert response.status_code in (301, 302)
    assert f"/recruiter-exit?participant_id={participant_id}" in response.location
    assert participant.end_time is not None


def test_prepare_commits_a_leftover_prepared_generic_recovery_plan(db_session):
    """A leftover prepared generic plan is committed instead of shown as chrome."""
    participant = _make_participant(page_uuid="page-1")
    experiment = get_experiment()
    with patch.object(
        experiment.recruiter, "shows_error_recovery_page", return_value=True
    ):
        Experiment._prepare_error_recovery_plan(
            experiment,
            experiment.recruiter,
            participant,
        )
    assert ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.PREPARED
    assert participant.early_exited is False

    Experiment._prepare_error_recovery_plan(
        experiment,
        experiment.recruiter,
        participant,
    )
    assert ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.COMMITTED
    assert participant.early_exited is True
    assert not isinstance(
        experiment.timeline.get_current_elt(experiment, participant),
        ErrorRecoveryPage,
    )


def test_prepared_recovery_is_the_first_early_exit_release_page(db_session):
    """Recruiters that present recovery UI keep it as the first release page."""
    participant = _make_participant(page_uuid="page-1")
    experiment = get_experiment()
    with patch.object(
        experiment.recruiter, "shows_error_recovery_page", return_value=True
    ):
        Experiment._prepare_error_recovery_plan(
            experiment,
            experiment.recruiter,
            participant,
        )
        db.session.commit()
        unique_id = participant.unique_id

        assert experiment.timeline.get_participant_branch(participant) == (
            "early_exit_release"
        )
        assert isinstance(
            experiment.timeline.get_current_elt(experiment, participant),
            ErrorRecoveryPage,
        )
        assert (
            ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.PREPARED
        )
        assert participant.early_exited is False

        with (
            Flask(__name__).test_request_context(
                f"/timeline?unique_id={unique_id}",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ),
            patch(
                "psynet.experiment.render_template_with_translations",
                return_value="stored recovery",
            ) as render,
        ):
            response = Experiment._route_timeline(experiment, participant, mode=None)

        assert response.status_code == 500
        assert render.called
        assert render.call_args.kwargs["automatic_exit_offer_id"] is not None
        assert (
            ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.PREPARED
        )
        assert participant.early_exited is False


def test_committed_return_for_bonus_continue_renders_payment_instructions(db_session):
    """Continue after return-for-bonus recovery must not re-render the error page."""
    participant = _make_participant(page_uuid="page-1")
    experiment = get_experiment()
    plan = ExitPlan.create(
        context=ExitContext.ERROR_RECOVERY,
        path=ExitPath.RETURN_FOR_BONUS,
        payment=PaymentDecision("returned", 0.0, 0.60),
        currency="$",
    )
    payment_copy = (
        "Please return your submission via the Prolific interface and click Next."
    )

    def release_participant(_experiment, _participant):
        return InfoPage(payment_copy, time_estimate=0.0)

    with (
        patch.object(
            experiment.recruiter, "shows_error_recovery_page", return_value=True
        ),
        patch.object(experiment.recruiter, "plan_exit", return_value=plan),
        patch.object(experiment.recruiter, "execute_early_exit_plan"),
        patch.object(
            experiment.recruiter, "release_participant", side_effect=release_participant
        ),
    ):
        Experiment._prepare_error_recovery_plan(
            experiment,
            experiment.recruiter,
            participant,
        )
        assert isinstance(
            experiment.timeline.get_current_elt(experiment, participant),
            ErrorRecoveryPage,
        )
        Experiment._commit_early_exit_plan(experiment, participant, plan)
        current = experiment.timeline.get_current_elt(experiment, participant)
        assert not isinstance(current, ErrorRecoveryPage)
        assert payment_copy in current.plain_text
        assert not Experiment._skipped_error_recovery_should_hand_off(
            experiment, participant
        )

        with (
            Flask(__name__).test_request_context(
                f"/timeline?unique_id={participant.unique_id}",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ),
            patch.object(InfoPage, "render", return_value=payment_copy) as render,
            patch.object(Experiment, "_render_error_page") as error_page,
        ):
            response = Experiment._route_timeline(experiment, participant, mode=None)

        assert response == payment_copy
        render.assert_called_once()
        error_page.assert_not_called()


def test_complete_timeline_visit_backstops_worker_complete(db_session):
    """Complete /timeline visits must stamp end_time before recruiter exit."""
    participant = _make_participant(complete=True, end_time=None, status="working")
    unique_id = participant.unique_id
    participant_id = participant.id
    experiment = get_experiment()

    with (
        Flask(__name__).test_request_context(f"/timeline?unique_id={unique_id}"),
        patch.object(experiment, "participant_task_completed"),
        patch("dallinger.experiment_server.worker_events.worker_function"),
    ):
        response = Experiment._route_timeline(experiment, participant, mode=None)

    assert response.status_code in (301, 302)
    assert f"/recruiter-exit?participant_id={participant_id}" in response.location

    db.session.commit()
    db.session.remove()
    reloaded = Participant.query.get(participant_id)
    assert reloaded.end_time is not None
    assert reloaded.status == "submitted"


def test_complete_timeline_visit_survives_worker_complete_closing_the_session(
    db_session,
):
    """Recruiter completion may close the session before the redirect is built."""
    participant = _make_participant(complete=True, end_time=None, status="working")
    unique_id = participant.unique_id
    participant_id = participant.id
    experiment = get_experiment()

    def close_session(*args, **kwargs):
        db.session.remove()

    with (
        Flask(__name__).test_request_context(f"/timeline?unique_id={unique_id}"),
        patch.object(experiment, "participant_task_completed"),
        patch(
            "dallinger.experiment_server.worker_events.worker_function",
            side_effect=close_session,
        ),
    ):
        response = Experiment._route_timeline(experiment, participant, mode=None)

    assert response.status_code in (301, 302)
    assert f"/recruiter-exit?participant_id={participant_id}" in response.location


def test_ensure_worker_complete_is_idempotent(db_session):
    participant = _make_participant(complete=True, end_time=None, status="working")
    experiment = get_experiment()

    with (
        patch.object(experiment, "participant_task_completed"),
        patch(
            "dallinger.experiment_server.worker_events.worker_function"
        ) as worker_function,
    ):
        Experiment._ensure_worker_complete(experiment, participant)
        first_end_time = participant.end_time
        assert first_end_time is not None
        Experiment._ensure_worker_complete(experiment, participant)
        assert participant.end_time == first_end_time
        assert worker_function.call_count == 1


def test_after_debrief_sets_complete_before_worker_complete(db_session):
    """Successful end marks complete while end_time is still unset."""
    participant = _make_participant(end_time=None, status="working")
    SuccessfulEndLogic().after_debrief(get_experiment(), participant)
    assert participant.complete is True
    assert participant.end_time is None
