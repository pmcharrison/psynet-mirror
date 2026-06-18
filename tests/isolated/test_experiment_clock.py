from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.exc

from psynet.experiment import Experiment


class UndefinedTable:
    pgcode = "42P01"


class OtherDatabaseError:
    pgcode = "99999"


def programming_error(orig):
    return sqlalchemy.exc.ProgrammingError("SELECT 1", {}, orig)


def test_check_barriers_skips_when_schema_is_not_ready(caplog):
    experiment = MagicMock()
    experiment.check_barriers.side_effect = programming_error(UndefinedTable())

    with patch("psynet.experiment._logged_barrier_schema_not_ready", False):
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
        if "database schema is not ready yet" in record.message
    ]
    assert len(matching_records) == 1
    assert all(record.exc_info is None for record in matching_records)


def test_check_barriers_raises_other_programming_errors():
    experiment = MagicMock()
    error = programming_error(OtherDatabaseError())
    experiment.check_barriers.side_effect = error

    with patch("psynet.experiment.is_experiment_launched", return_value=True):
        with patch("psynet.experiment.get_experiment", return_value=experiment):
            with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
                Experiment._check_barriers()

    assert exc_info.value is error


def test_check_sync_groups_skips_when_schema_is_not_ready(caplog):
    experiment = MagicMock()
    experiment.check_sync_groups.side_effect = programming_error(UndefinedTable())

    with patch("psynet.experiment._logged_sync_group_schema_not_ready", False):
        with patch("psynet.experiment.is_experiment_launched", return_value=True):
            with patch("psynet.experiment.get_experiment", return_value=experiment):
                with patch("psynet.experiment.db.session.rollback") as rollback:
                    with caplog.at_level("WARNING"):
                        Experiment._check_sync_groups()
                        Experiment._check_sync_groups()

    assert rollback.call_count == 2
    matching_records = [
        record
        for record in caplog.records
        if "sync group check" in record.message
        and "database schema is not ready yet" in record.message
    ]
    assert len(matching_records) == 1
    assert all(record.exc_info is None for record in matching_records)


def test_check_sync_groups_raises_other_programming_errors():
    experiment = MagicMock()
    error = programming_error(OtherDatabaseError())
    experiment.check_sync_groups.side_effect = error

    with patch("psynet.experiment.is_experiment_launched", return_value=True):
        with patch("psynet.experiment.get_experiment", return_value=experiment):
            with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
                Experiment._check_sync_groups()

    assert exc_info.value is error
