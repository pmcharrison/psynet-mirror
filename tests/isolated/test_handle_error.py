import time

import pytest
from dallinger import db

from psynet.error import ErrorRecord
from psynet.process import WorkerAsyncProcess
from psynet.pytest_psynet import path_to_test_experiment


def task():
    raise ValueError("process failed")


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
