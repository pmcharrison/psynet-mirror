import pexpect


def _resolve_timeout(process, timeout):
    if timeout is None:
        return process.timeout
    return timeout


def wait_and_collect_output(process, timeout=None):
    resolved_timeout = _resolve_timeout(process, timeout)
    try:
        process.expect(pexpect.EOF, timeout=resolved_timeout)
    except pexpect.exceptions.TIMEOUT:
        pass

    before = process.before
    if isinstance(before, bytes):
        output = before.decode("utf-8")
    else:
        output = before or ""

    process.wait()
    close_popen_spawn_streams(process)
    return output


def close_popen_spawn_streams(process):
    for stream in (process.proc.stdin, process.proc.stdout, process.proc.stderr):
        if stream and not stream.closed:
            stream.close()
