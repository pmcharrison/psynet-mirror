import signal
import subprocess

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


def finalize_popen_spawn(process):
    if process.proc.poll() is None:
        return None
    try:
        exit_code = process.wait()
    except AttributeError:
        exit_code = process.proc.wait()
    close_popen_spawn_streams(process)
    return exit_code


def terminate_popen_spawn(process, timeout=5):
    if process.proc.poll() is not None:
        return finalize_popen_spawn(process)

    for sig in (signal.SIGINT, signal.SIGKILL):
        try:
            process.kill(sig)
        except OSError:
            continue
        try:
            process.proc.wait(timeout=timeout)
            break
        except subprocess.TimeoutExpired:
            continue

    if process.proc.poll() is None:
        close_popen_spawn_streams(process)
        return None

    return finalize_popen_spawn(process)
