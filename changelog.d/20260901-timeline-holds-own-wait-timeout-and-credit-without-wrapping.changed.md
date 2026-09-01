Default ``wait_while`` and barrier waits are now a single timeline hold, which owns timeout, progress, and time credit instead of wrapping ``while_loop``.
