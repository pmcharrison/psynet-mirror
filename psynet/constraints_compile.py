"""Constraints-file generation and freshness checks for PsyNet experiments.

This module provides :func:`generate_constraints_file`, which produces a
``constraints.txt`` from ``requirements.txt`` using Dallinger's standalone
constraints script via ``uv run``, and :func:`constraints_are_up_to_date`,
which decides whether an existing lockfile still matches ``requirements.txt``.

That script (PEP 723, dependencies only ``click`` and ``requests``) implements
the real lock policy: resolve against the Dallinger ``dev-requirements.txt``
for the Dallinger version implied by the experiment requirements, using
``.python-version``. It does not require ``psynet[experiment]`` or an imported
Dallinger package, so thin-bootstrap ``psynet setup`` can lock before
``uv pip sync``.

When Dallinger is installed (editable or otherwise), its local
``dallinger.constraints`` script is used so generation matches the installed
package. Otherwise the script is fetched from a pinned Dallinger release tag
on GitHub (never ``master``).

Callers
-------
- ``psynet.bootstrap_cli`` – ``generate-constraints`` command.
- ``psynet.experiment_setup._ensure_constraints_up_to_date`` – called during
  ``psynet setup`` to create or refresh the lockfile when missing or stale.
- ``psynet.command_line._check_constraints`` – deploy/debug verification.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from hashlib import md5
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import click

# Pinned release used when Dallinger is not installed (thin bootstrap). Keep in
# sync with the lower end of PsyNet's supported Dallinger range in pyproject.toml.
_DALLINGER_CONSTRAINTS_REF = "v12.2.1"
_DALLINGER_CONSTRAINTS_URL = (
    "https://raw.githubusercontent.com/Dallinger/Dallinger/"
    f"{_DALLINGER_CONSTRAINTS_REF}/dallinger/constraints.py"
)


def constraints_are_up_to_date(
    *,
    requirements_path: Path | None = None,
    constraints_path: Path | None = None,
) -> bool:
    """Return whether ``constraints.txt`` matches ``requirements.txt``.

    A lockfile is up to date when it exists, is non-empty, and embeds the MD5
    digest of the current ``requirements.txt`` contents (the same signal
    ``psynet check-constraints`` uses).
    """
    requirements_path = requirements_path or Path("requirements.txt")
    constraints_path = constraints_path or Path("constraints.txt")
    if not requirements_path.is_file():
        return False
    if not constraints_path.is_file() or constraints_path.stat().st_size == 0:
        return False
    requirements_hash = md5(requirements_path.read_bytes()).hexdigest()
    return requirements_hash in constraints_path.read_text()


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


def _dallinger_constraints_script() -> str:
    """Return and describe the Dallinger constraints script used by ``uv``.

    Prefers the script from an installed Dallinger package so generation matches
    that package. Thin-bootstrap environments (Dallinger not installed) use a
    pinned GitHub release URL instead of ``master``.
    """
    local_script = _installed_dallinger_constraints_script()
    if local_script is not None:
        click.echo(f"Using constraints script from installed Dallinger: {local_script}")
        return str(local_script)

    click.echo(
        "Using Dallinger constraints script from GitHub "
        f"({_DALLINGER_CONSTRAINTS_REF}): {_DALLINGER_CONSTRAINTS_URL}"
    )
    return _DALLINGER_CONSTRAINTS_URL


def _installed_dallinger_constraints_script() -> Path | None:
    """Return ``dallinger.constraints`` when Dallinger is installed."""
    try:
        distribution("dallinger")
    except PackageNotFoundError:
        return None

    spec = importlib.util.find_spec("dallinger.constraints")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin)
