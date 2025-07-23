from contextlib import contextmanager
from functools import wraps

import dallinger.db


@contextmanager
def transaction(commit: bool = True):
    """
    Context manager to handle database transactions.

    The crucial behaviour here is that ``session.remove()`` is called internally
    once the context is exited, which ensures that the database session is closed.
    This ensures that we don't get problems with unintended long-lived database sessions
    that can lead to performance issues including deadlocks.

    As opposed to ``dallinger.db.session_scope``, we by default commit the transaction
    at the end of the context. In general we want to discourage users from calling ``session.commit()``
    themselves, and just use this context manager to handle transactions automatically.
    This should be best for atomicity and performance.
    """
    with dallinger.db.sessions_scope(dallinger.db.session):
        yield
        if commit:
            dallinger.db.session.commit()


def with_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return wrapper
