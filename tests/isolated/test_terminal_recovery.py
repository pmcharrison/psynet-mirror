"""Focused contracts for tracked fatal recovery and completion backstops."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dallinger import db
from flask import Flask

from psynet.end import ErrorRecoveryPage, SuccessfulEndLogic
from psynet.exit import ExitPlan, ExitPlanStatus
from psynet.experiment import Experiment, get_experiment
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
        patch.object(experiment.timeline, "get_current_elt", return_value=event),
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
    assert "error_recovery" in (after_fatal.failure_tags or [])
    assert "ValueError" in (after_fatal.failure_tags or [])


def test_prepared_recovery_is_the_first_early_exit_release_page(db_session):
    """Preparing tracked recovery moves the participant to its timeline page."""
    participant = _make_participant(page_uuid="page-1")
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
    assert isinstance(
        experiment.timeline.get_current_elt(experiment, participant),
        ErrorRecoveryPage,
    )
    assert ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.PREPARED
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
    assert ExitPlan.from_dict(participant.exit_plan).status is ExitPlanStatus.PREPARED
    assert participant.early_exited is False


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
