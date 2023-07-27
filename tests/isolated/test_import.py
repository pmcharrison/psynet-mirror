import pexpect


def test_import():
    # sqlalchemy can throw registration errors if not all dependent modules are loaded at the time of
    # class instantiation.
    # At some point this caused the following import to throw an error if ``psynet.experiment``
    # had not already been imported.

    # We need to run this in a subprocess to make sure that no other packages are imported
    p = pexpect.spawn(
        'python3 -c "from psynet.trial.chain import ChainNetwork"', timeout=10
    )

    # Print the output of this command
    while not p.eof():
        line = p.readline().decode("utf-8")
        print(line, end="")
    p.close()

    # Assert that the command ran successfully
    assert p.exitstatus == 0
