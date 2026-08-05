"""Constraints-file generation for PsyNet experiments.

This module provides :func:`generate_constraints_file`, which produces a
``constraints.txt`` from ``requirements.txt`` using Dallinger's standalone
constraints script via ``uv run``.

That script (PEP 723, dependencies only ``click`` and ``requests``) implements
the real lock policy: resolve against the Dallinger ``dev-requirements.txt``
for the Dallinger version implied by the experiment requirements, using
``.python-version``. It does not require ``psynet[experiment]`` or an imported
Dallinger package, so thin-bootstrap ``psynet setup`` can lock before
``uv pip sync``.

When Dallinger is installed (editable or via ``psynet[experiment]``), the
installed ``dallinger.constraints`` module is preferred so local Dallinger
checkouts are used. Otherwise PsyNet's vendored copy under
``psynet/resources/dallinger_constraints.py`` is used.

Callers
-------
- ``psynet.bootstrap_cli`` – ``generate-constraints`` command.
- ``psynet.experiment_setup._generate_constraints_if_missing`` – called
  during ``psynet setup`` to create the initial constraints file.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import click

_VENDORED_CONSTRAINTS_SCRIPT = (
    Path(__file__).resolve().parent / "resources" / "dallinger_constraints.py"
)


def generate_constraints_file() -> None:
    """Generate ``constraints.txt`` from ``requirements.txt`` in the CWD.

    Runs Dallinger's standalone constraints script with ``uv run … generate``.

    Raises
    ------
    click.ClickException
        If the requirements file is missing, ``uv`` is unavailable, or the
        constraints script fails.
    """
    requirements_path = Path("requirements.txt")
    if not requirements_path.is_file():
        raise click.ClickException(
            "requirements.txt not found. Create one before generating constraints."
        )

    if shutil.which("uv") is None:
        raise click.ClickException(
            "Could not find 'uv' on PATH. Install it with 'pip install uv' "
            "and try again."
        )

    script = _dallinger_constraints_script()
    try:
        subprocess.run(
            ["uv", "run", str(script), "generate"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            "Failed to generate constraints.txt via Dallinger's constraints "
            f"script (exit code {exc.returncode})."
        ) from exc

    constraints_path = Path("constraints.txt")
    if not constraints_path.is_file() or constraints_path.stat().st_size == 0:
        raise click.ClickException(
            "Failed to generate a non-empty constraints.txt file."
        )


def _dallinger_constraints_script() -> Path:
    """Return the Dallinger constraints script to run with ``uv run``.

    Prefers an installed ``dallinger.constraints`` module when importable so
    editable Dallinger checkouts are used; otherwise the vendored PsyNet copy.
    """
    spec = importlib.util.find_spec("dallinger.constraints")
    if spec is not None and spec.origin is not None:
        return Path(spec.origin)

    if not _VENDORED_CONSTRAINTS_SCRIPT.is_file():
        raise click.ClickException(
            "Vendored Dallinger constraints script is missing from the PsyNet "
            f"install ({_VENDORED_CONSTRAINTS_SCRIPT})."
        )
    return _VENDORED_CONSTRAINTS_SCRIPT
