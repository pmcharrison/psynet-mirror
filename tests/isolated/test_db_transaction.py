import pytest
from dallinger import db
from sqlalchemy import Column, String
from sqlalchemy.orm import object_session

from psynet.data import SQLBase
from psynet.db import (
    _set_transaction_lock_timeout,
    read_only_transaction,
    transaction,
)
from psynet.pytest_psynet import path_to_test_experiment


class DummyTransactionModel(SQLBase):
    __tablename__ = "dummy_transaction_model"

    id = Column(String, primary_key=True)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_nested_transaction_reuses_session(db_session):
    DummyTransactionModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)

    with transaction():
        obj = DummyTransactionModel(id="nested-session")
        db.session.add(obj)
        db.session.flush()

        outer_session = object_session(obj)
        assert outer_session is db.session()

        with transaction(commit=False):
            assert object_session(obj) is outer_session
            assert db.session() is outer_session

        assert object_session(obj) is outer_session

    assert object_session(obj) is None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_nested_transaction_commit_false_does_not_persist(db_session):
    DummyTransactionModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)

    with transaction(commit=False):
        obj = DummyTransactionModel(id="nested-no-commit")
        db.session.add(obj)
        db.session.flush()

        with transaction(commit=False):
            assert object_session(obj) is db.session()

    with transaction():
        assert DummyTransactionModel.query.get("nested-no-commit") is None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_read_only_transaction_starts_after_write_commit(db_session):
    DummyTransactionModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)

    with transaction():
        db.session.add(DummyTransactionModel(id="rendered"))
        db.session.commit()

        with read_only_transaction() as session:
            assert not session.autoflush
            assert DummyTransactionModel.query.get("rendered") is not None

        assert not db.session().in_transaction()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_read_only_transaction_rejects_pending_orm_writes(db_session):
    DummyTransactionModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)

    with transaction():
        db.session.commit()
        with pytest.raises(RuntimeError, match="attempted to mutate ORM state"):
            with read_only_transaction():
                db.session.add(DummyTransactionModel(id="render-write"))

    assert DummyTransactionModel.query.get("render-write") is None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_read_only_transaction_rejects_nested_commit(db_session):
    with transaction():
        db.session.commit()
        with read_only_transaction():
            with pytest.raises(RuntimeError, match="cannot commit"):
                db.session.commit()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_transaction_lock_timeout_is_scoped_locally(db_session):
    with transaction():
        _set_transaction_lock_timeout(5)
        timeout = db.session.execute("SHOW lock_timeout").scalar()

    assert timeout == "5s"
