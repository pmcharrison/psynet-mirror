import pytest
import sqlalchemy.exc

from psynet import pytest_psynet


class FakeDeadlock(Exception):
    pgcode = pytest_psynet.DEADLOCK_PGCODE


class FakeOtherError(Exception):
    pgcode = "55006"  # object_in_use


def operational_error(orig):
    return sqlalchemy.exc.OperationalError("DROP TABLE ...", None, orig)


@pytest.fixture
def quiet_db(monkeypatch):
    """Stub out init_db used by init_db_with_retries."""
    import dallinger.db

    return dallinger.db


def test_retries_on_deadlock_then_succeeds(quiet_db, monkeypatch):
    calls = []

    def fake_init_db(drop_all=False):
        calls.append(drop_all)
        if len(calls) == 1:
            raise operational_error(FakeDeadlock())
        return "session"

    monkeypatch.setattr(quiet_db, "init_db", fake_init_db)
    monkeypatch.setattr("sqlalchemy.orm.session.close_all_sessions", lambda: None)
    assert pytest_psynet.init_db_with_retries(wait_sec=0) == "session"
    assert calls == [True, True]


def test_non_deadlock_error_propagates_immediately(quiet_db, monkeypatch):
    calls = []

    def fake_init_db(drop_all=False):
        calls.append(drop_all)
        raise operational_error(FakeOtherError())

    monkeypatch.setattr(quiet_db, "init_db", fake_init_db)
    with pytest.raises(sqlalchemy.exc.OperationalError):
        pytest_psynet.init_db_with_retries(wait_sec=0)
    assert len(calls) == 1


def test_persistent_deadlock_raises_after_max_attempts(quiet_db, monkeypatch):
    calls = []

    def fake_init_db(drop_all=False):
        calls.append(drop_all)
        raise operational_error(FakeDeadlock())

    monkeypatch.setattr(quiet_db, "init_db", fake_init_db)
    monkeypatch.setattr("sqlalchemy.orm.session.close_all_sessions", lambda: None)
    with pytest.raises(sqlalchemy.exc.OperationalError):
        pytest_psynet.init_db_with_retries(max_attempts=3, wait_sec=0)
    assert len(calls) == 3


def test_closes_sessions_between_deadlock_retries(quiet_db, monkeypatch):
    """Failed transactions must be cleared before the next drop_all attempt."""
    calls = []
    close_calls = []

    def fake_init_db(drop_all=False):
        calls.append(drop_all)
        if len(calls) == 1:
            raise operational_error(FakeDeadlock())
        return "session"

    monkeypatch.setattr(quiet_db, "init_db", fake_init_db)
    monkeypatch.setattr(
        "sqlalchemy.orm.session.close_all_sessions",
        lambda: close_calls.append("close"),
    )
    assert pytest_psynet.init_db_with_retries(wait_sec=0) == "session"
    assert calls == [True, True]
    assert close_calls == ["close"]


def test_deadlock_pgcode_matches_psycopg2_deadlock_class():
    """Pin the driver contract: SQLSTATE 40P01 is psycopg2's DeadlockDetected.

    Green CI pipelines only exercise the no-deadlock path, so if the driver
    ever stopped exposing ``pgcode`` this way, retries would silently stop
    working. This test makes such a change visible.
    """
    import psycopg2.errors

    assert (
        psycopg2.errors.lookup(pytest_psynet.DEADLOCK_PGCODE)
        is psycopg2.errors.DeadlockDetected
    )
