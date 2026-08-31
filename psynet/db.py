from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

import dallinger.db

_transaction_depth = ContextVar("psynet_transaction_depth", default=0)


# #region agent log
def _agent_dbg(hypothesis_id, location, message, data=None):
    """Temporary NDJSON debug logger for concurrency stall investigation."""
    import json
    import threading
    import time

    try:
        payload = {
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": {
                **(data or {}),
                "thread": threading.current_thread().name,
                "tid": threading.get_ident(),
            },
            "timestamp": int(time.time() * 1000),
        }
        with open("/opt/cursor/logs/debug.log", "a") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


# #endregion


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
    # #region agent log
    if depth == 0:
        _agent_dbg(
            "E",
            "db.py:transaction",
            "txn_enter",
            {"depth": depth, "commit": commit, "session_id": id(dallinger.db.session())},
        )
    # #endregion
    try:
        if depth == 0:
            with dallinger.db.sessions_scope(dallinger.db.session):
                yield
                if commit:
                    # #region agent log
                    _agent_dbg(
                        "E",
                        "db.py:transaction",
                        "txn_commit",
                        {
                            "depth": depth,
                            "session_id": id(dallinger.db.session()),
                        },
                    )
                    # #endregion
                    dallinger.db.session.commit()
        else:
            yield
            if commit:
                dallinger.db.session.commit()
    except Exception as exc:
        # #region agent log
        if depth == 0:
            _agent_dbg(
                "E",
                "db.py:transaction",
                "txn_error",
                {"depth": depth, "error": repr(exc)},
            )
        # #endregion
        raise
    finally:
        # #region agent log
        if depth == 0:
            _agent_dbg(
                "E",
                "db.py:transaction",
                "txn_exit",
                {"depth": depth, "session_id": id(dallinger.db.session())},
            )
        # #endregion
        _transaction_depth.reset(token)


def with_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return wrapper
