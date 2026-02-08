import shlex

from pexpect import popen_spawn

from psynet.pexpect_utils import wait_and_collect_output


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
    output = wait_and_collect_output(p, timeout=10)
    print(output, end="")

    # Assert that the command ran successfully
    assert p.exitstatus == 0
