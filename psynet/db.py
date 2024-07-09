from contextlib import contextmanager
from functools import wraps

import dallinger.db


@contextmanager
def transaction():
    # Ideally we would make a new session here, but it's problematic for back-compatability.
    # Prior code will use ``dallinger.db.session`` and we can't change that.
    # One day though we should try and do something like thia:
    #
    # session = session_factory()
    # try:
    #     yield session
    #     session.commit()
    # except:
    #     session.rollback()
    #     raise
    # finally:
    #     session.close()
    session = dallinger.db.session
    try:
        session.commit()
        with forbid_committing("You can't commit inside a transaction"):
            yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


@contextmanager
def forbid_committing(message):
    session = dallinger.db.session
    original_commit = session.commit
    session.commit = _forbidden(message)
    try:
        yield
    finally:
        session.commit = original_commit


def _forbidden(message):
    def f(*args, **kwargs):
        raise RuntimeError(message)

    return f


def with_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return wrapper
