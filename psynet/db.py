from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

import dallinger.db
from sqlalchemy import event, text

_transaction_depth = ContextVar("psynet_transaction_depth", default=0)
_read_only_render_depth = ContextVar("psynet_read_only_render_depth", default=0)


@event.listens_for(dallinger.db.session, "before_commit")
def _prevent_render_commit(session):
    if _read_only_render_depth.get() > 0:
        raise RuntimeError("Timeline rendering cannot commit database transactions.")


@event.listens_for(dallinger.db.session, "before_flush")
def _prevent_render_flush(session, flush_context, instances):
    if _read_only_render_depth.get() > 0 and (
        session.new or session.dirty or session.deleted
    ):
        raise RuntimeError("Timeline rendering cannot flush ORM mutations.")


@contextmanager
def transaction(commit: bool = True):
    """
    Context manager to handle database transactions.

    The crucial behaviour here is that ``session.remove()`` is called internally
    once the *outermost* context is exited, which ensures that the database session
    is closed. Nested ``transaction()`` calls reuse the existing session to avoid
    prematurely detaching ORM objects, while still preventing unintended long-lived
    sessions that can lead to performance issues including deadlocks.

    As opposed to ``dallinger.db.session_scope``, we by default commit the transaction
    at the end of the context. In general we want to discourage users from calling ``session.commit()``
    themselves, and just use this context manager to handle transactions automatically.
    This should be best for atomicity and performance.
    """
    depth = _transaction_depth.get()
    token = _transaction_depth.set(depth + 1)
    try:
        if depth == 0:
            with dallinger.db.sessions_scope(dallinger.db.session):
                yield
                if commit:
                    dallinger.db.session.commit()
        else:
            yield
            if commit:
                dallinger.db.session.commit()
    finally:
        _transaction_depth.reset(token)


def with_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return wrapper


def _set_transaction_lock_timeout(seconds, session=None):
    """Bound PostgreSQL lock waits in the current transaction."""
    if session is None:
        session = dallinger.db.session
    session.execute(
        text("SELECT set_config('lock_timeout', :timeout, true)"),
        {"timeout": f"{seconds}s"},
    )


@contextmanager
def read_only_transaction():
    """Run rendering in a fresh read-only transaction on the scoped session."""
    session = dallinger.db.session()
    if session.in_transaction():
        raise RuntimeError("Read-only rendering requires a committed write phase.")

    previous_autoflush = session.autoflush
    token = _read_only_render_depth.set(_read_only_render_depth.get() + 1)
    session.autoflush = False
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
        pending = {
            "new": [type(obj).__name__ for obj in session.new],
            "dirty": [type(obj).__name__ for obj in session.dirty],
            "deleted": [type(obj).__name__ for obj in session.deleted],
        }
        if any(pending.values()):
            raise RuntimeError(
                f"Timeline rendering attempted to mutate ORM state: {pending}."
            )
    finally:
        session.rollback()
        session.autoflush = previous_autoflush
        _read_only_render_depth.reset(token)
