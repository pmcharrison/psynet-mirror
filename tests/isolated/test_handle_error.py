import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dallinger import db

from psynet.error import ErrorRecord
from psynet.experiment import Experiment
from psynet.process import WorkerAsyncProcess
from psynet.pytest_psynet import path_to_test_experiment
from psynet.recruiters import DevLucidRecruiter


def task():
    raise ValueError("process failed")


def test_handled_error_page_recovers_participant_and_uses_recruiter_policy():
    participant = SimpleNamespace(assignment_id="assignment-1")
    recruiter = MagicMock()
    recruiter.external_submit_url.return_value = "https://example.test/submit"
    experiment = SimpleNamespace(recruiter=recruiter)
    handled_error = Experiment.HandledError(participant_id=42)

    with (
        patch.object(
            Experiment,
            "get_participant_from_participant_id",
            return_value=participant,
        ) as get_participant,
        patch("psynet.experiment.get_experiment", return_value=experiment),
        patch.object(Experiment, "error_page", return_value="response") as error_page,
    ):
        assert handled_error.error_page() == "response"

    get_participant.assert_called_once_with(42)
    recruiter.on_error_page.assert_called_once_with(participant)
    error_page.assert_called_once_with(
        participant=participant,
        request_data="",
        recruiter=recruiter,
        external_submit_url="https://example.test/submit",
        compensate=True,
    )


def test_handled_error_page_preserves_lucid_uncompensated_policy():
    participant = SimpleNamespace(assignment_id="rid-1")
    recruiter = MagicMock(spec=DevLucidRecruiter)
    recruiter.external_submit_url.return_value = "https://example.test/terminate"
    experiment = SimpleNamespace(recruiter=recruiter)

    with (
        patch.object(
            Experiment,
            "get_participant_from_participant_id",
            return_value=participant,
        ),
        patch("psynet.experiment.get_experiment", return_value=experiment),
        patch.object(Experiment, "error_page", return_value="response") as error_page,
    ):
        assert Experiment.HandledError(participant_id=42).error_page() == "response"

    recruiter.set_termination_details.assert_called_once_with(
        "rid-1", "error-page_route"
    )
    error_page.assert_called_once_with(
        participant=participant,
        request_data="",
        recruiter=recruiter,
        external_submit_url="https://example.test/terminate",
        compensate=False,
    )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
def test_handle_error_rollback_and_record(db_session, launched_experiment, trial):
    trial_id = trial.id
    node_id = trial.node.id

    trial.answer = "original"
    db.session.commit()

    try:
        trial.answer = "new"
        raise ValueError("test error")
    except ValueError as e:
        launched_experiment.handle_error(e, trial=trial)

    db.session.refresh(trial)

    # Check that the trial is rolled back to its original state
    assert trial.answer == "original"

    error_record = ErrorRecord.query.one()
    assert error_record.trial_id == trial_id
    assert error_record.node_id == node_id
    assert error_record.kind == "ValueError"
    assert error_record.message == "test error"


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
def test_handle_error_async_process(db_session, launched_experiment, trial):
    process = WorkerAsyncProcess(function=task, trial=trial)
    db.session.commit()

    time.sleep(1)

    assert process.failed

    error_record = ErrorRecord.query.one()
    assert error_record.process_id == process.id
    assert error_record.trial_id == trial.id
