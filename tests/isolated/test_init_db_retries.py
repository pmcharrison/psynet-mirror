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
    """Stub out the real database interactions of init_db_with_retries."""
    import dallinger.db

    monkeypatch.setattr(
        pytest_psynet, "terminate_other_postgres_connections", lambda: None
    )
    monkeypatch.setattr(
        dallinger.db, "session", type("S", (), {"rollback": staticmethod(lambda: None)})
    )
    return dallinger.db


def test_retries_on_deadlock_then_succeeds(quiet_db, monkeypatch):
    calls = []

    def fake_init_db(drop_all=False):
        calls.append(drop_all)
        if len(calls) == 1:
            raise operational_error(FakeDeadlock())
        return "session"

    monkeypatch.setattr(quiet_db, "init_db", fake_init_db)
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
    with pytest.raises(sqlalchemy.exc.OperationalError):
        pytest_psynet.init_db_with_retries(max_attempts=3, wait_sec=0)
    assert len(calls) == 3
