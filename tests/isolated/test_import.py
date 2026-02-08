import subprocess


def test_import():
    # sqlalchemy can throw registration errors if not all dependent modules are loaded at the time of
    # class instantiation.
    # At some point this caused the following import to throw an error if ``psynet.experiment``
    # had not already been imported.

    # We need to run this in a subprocess to make sure that no other packages are imported
    result = subprocess.run(
        ["python3", "-c", "from psynet.trial.chain import ChainNetwork"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")

    assert result.returncode == 0
