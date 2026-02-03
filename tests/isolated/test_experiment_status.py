import datetime

import pytest
from dallinger import db

from psynet.experiment import ExperimentStatus, get_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.redis import redis_vars


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_test_experiment("consents")],
    indirect=True,
)
def test_record_experiment_status_uses_row_timestamp(
    in_experiment_directory, db_session, deployment_info
):
    exp = get_experiment()
    creation_time = datetime.datetime.now() - datetime.timedelta(days=7)
    redis_vars.set("creation_time", creation_time)
    redis_vars.set("base_url", "http://localhost:5000")

    exp.record_experiment_status()
    db.session.commit()

    status = ExperimentStatus.query.order_by(ExperimentStatus.id.desc()).first()
    assert status is not None
    status_creation_time = status.creation_time
    if status_creation_time.tzinfo is not None:
        status_creation_time = status_creation_time.replace(tzinfo=None)

    assert status_creation_time > creation_time
