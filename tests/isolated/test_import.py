import shlex

import pexpect.exceptions
from pexpect import popen_spawn


def test_import():
    # sqlalchemy can throw registration errors if not all dependent modules are loaded at the time of
    # class instantiation.
    # At some point this caused the following import to throw an error if ``psynet.experiment``
    # had not already been imported.

    # We need to run this in a subprocess to make sure that no other packages are imported
    # Use PopenSpawn instead of spawn to avoid forkpty() deprecation warning
    # in Python 3.13+ multi-threaded processes.
    cmd = 'python3 -c "from psynet.trial.chain import ChainNetwork"'
    p = popen_spawn.PopenSpawn(shlex.split(cmd), timeout=10)

    # Print the output of this command
    # PopenSpawn doesn't have eof(), so use expect() to wait for EOF
    try:
        p.expect(pexpect.EOF, timeout=10)
    except pexpect.exceptions.TIMEOUT:
        pass

    # Read any remaining buffered output
    output = p.before.decode("utf-8") if p.before else ""
    print(output, end="")

    p.wait()
    for stream in (p.proc.stdin, p.proc.stdout, p.proc.stderr):
        if stream and not stream.closed:
            stream.close()

    # Assert that the command ran successfully
    assert p.exitstatus == 0
