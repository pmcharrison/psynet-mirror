from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.exc

from psynet.experiment import Experiment


class DeadlockDetected:
    pgcode = "40P01"


class OtherDatabaseError:
    pgcode = "99999"


def operational_error(orig):
    return sqlalchemy.exc.OperationalError("SELECT 1", {}, orig)


def test_check_barriers_skips_deadlocks_during_launch(caplog):
    experiment = MagicMock()
    experiment.check_barriers.side_effect = operational_error(DeadlockDetected())

    with patch("psynet.experiment._logged_barrier_database_busy", False):
        with patch("psynet.experiment.is_experiment_launched", return_value=True):
            with patch("psynet.experiment.get_experiment", return_value=experiment):
                with patch("psynet.experiment.db.session.rollback") as rollback:
                    with caplog.at_level("WARNING"):
                        Experiment._check_barriers()
                        Experiment._check_barriers()

    assert rollback.call_count == 2
    matching_records = [
        record
        for record in caplog.records
        if "barrier check" in record.message
        and "database is busy during launch" in record.message
    ]
    assert len(matching_records) == 1
    assert all(record.exc_info is None for record in matching_records)


def test_check_barriers_raises_other_operational_errors():
    experiment = MagicMock()
    error = operational_error(OtherDatabaseError())
    experiment.check_barriers.side_effect = error

    with patch("psynet.experiment.is_experiment_launched", return_value=True):
        with patch("psynet.experiment.get_experiment", return_value=experiment):
            with pytest.raises(sqlalchemy.exc.OperationalError) as exc_info:
                Experiment._check_barriers()

    assert exc_info.value is error
