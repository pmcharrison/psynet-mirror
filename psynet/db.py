from contextlib import contextmanager
from functools import wraps

import dallinger.db


@contextmanager
def transaction():
    with dallinger.db.sessions_scope():
        yield
        dallinger.db.session.commit()


def with_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return wrapper
