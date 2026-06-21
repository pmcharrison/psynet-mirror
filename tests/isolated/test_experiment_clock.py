from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy.exc

from psynet.experiment import Experiment


class UndefinedTable:
    pgcode = "42P01"


class OtherDatabaseError:
    pgcode = "99999"


class UndefinedColumn:
    pgcode = "42703"

    def __str__(self):
        return 'column "missing_column" does not exist'


def programming_error(orig):
    return sqlalchemy.exc.ProgrammingError("SELECT 1", {}, orig)


CHECKS = [
    pytest.param(
        Experiment._check_barriers,
        "check_barriers",
        "barrier check",
        id="barriers",
    ),
    pytest.param(
        Experiment._check_sync_groups,
        "check_sync_groups",
        "sync group check",
        id="sync-groups",
    ),
]


def run_clock_check(check, experiment):
    with patch("psynet.experiment.is_experiment_launched", return_value=True):
        with patch("psynet.experiment.get_experiment", return_value=experiment):
            check()


@pytest.mark.parametrize("check, method_name, log_label", CHECKS)
def test_clock_check_skips_when_schema_is_not_ready(
    check, method_name, log_label, caplog
):
    experiment = MagicMock()
    getattr(experiment, method_name).side_effect = programming_error(UndefinedTable())

    with patch("psynet.experiment._schema_not_ready_warned", set()):
        with patch("psynet.experiment.db.session.rollback") as rollback:
            with caplog.at_level("WARNING"):
                run_clock_check(check, experiment)
                run_clock_check(check, experiment)

    assert rollback.call_count == 2
    matching_records = [
        record
        for record in caplog.records
        if log_label in record.message
        and "database schema is not ready yet" in record.message
    ]
    assert len(matching_records) == 1
    assert all(record.exc_info is None for record in matching_records)


@pytest.mark.parametrize("check, method_name, _log_label", CHECKS)
def test_clock_check_raises_other_programming_errors(check, method_name, _log_label):
    experiment = MagicMock()
    error = programming_error(OtherDatabaseError())
    getattr(experiment, method_name).side_effect = error

    with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
        run_clock_check(check, experiment)

    assert exc_info.value is error


def test_check_barriers_raises_non_table_errors_with_does_not_exist_message():
    experiment = MagicMock()
    error = programming_error(UndefinedColumn())
    experiment.check_barriers.side_effect = error

    with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
        run_clock_check(Experiment._check_barriers, experiment)

    assert exc_info.value is error
