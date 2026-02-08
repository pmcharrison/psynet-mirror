import inspect

import pexpect

try:
    _SUPPORTS_NATIVE_PTY_FORK = (
        "use_native_pty_fork" in inspect.signature(pexpect.spawn).parameters
    )
except (TypeError, ValueError):
    _SUPPORTS_NATIVE_PTY_FORK = False


def spawn_pexpect(*args, **kwargs):
    if _SUPPORTS_NATIVE_PTY_FORK:
        kwargs.setdefault("use_native_pty_fork", False)
    return pexpect.spawn(*args, **kwargs)
