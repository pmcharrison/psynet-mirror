import pytest
from dallinger import db

from psynet.error import ErrorRecord
from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
def test_handle_error(db_session, launched_experiment, trial):
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
