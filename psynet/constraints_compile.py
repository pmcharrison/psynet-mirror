"""Constraints-file generation for PsyNet experiments.

This module provides :func:`generate_constraints_file`, which can produce a
``constraints.txt`` from ``requirements.txt`` with or without a full Dallinger
installation.

Strategy
--------
1. **Preferred path** – When ``dallinger.command_line`` is importable (i.e. the
   ``psynet[experiment]`` extra is installed), the existing Dallinger
   constraints-generation machinery is reused unchanged.  This preserves the
   exact same ``dev-requirements`` pinning behaviour that PsyNet experiments
   have always used.

2. **Bootstrap fallback** – When Dallinger is not available, ``uv`` must be on
   ``PATH``.  We invoke ``uv pip compile requirements.txt -o constraints.txt``
   and then embed the MD5 hex digest of ``requirements.txt`` as a comment so
   that PsyNet's ``_check_constraints`` function recognises the file as current.

Callers
-------
- ``psynet.bootstrap_cli`` – ``generate-constraints`` command.
- ``psynet.experiment_setup._generate_constraints_if_missing`` – called
  during ``psynet setup`` to create the initial constraints file.
"""

from __future__ import annotations

import shutil
import subprocess
from hashlib import md5
from pathlib import Path

import click


def generate_constraints_file() -> None:
    """Generate ``constraints.txt`` from ``requirements.txt`` in the CWD.

    Tries Dallinger's generator first; falls back to a bare ``uv pip compile``
    when Dallinger is not installed.

    Raises
    ------
    click.ClickException
        If the requirements file is missing, uv is unavailable in the fallback
        path, or the compilation command fails.
    """
    requirements_path = Path("requirements.txt")
    if not requirements_path.is_file():
        raise click.ClickException(
            "requirements.txt not found. Create one before generating constraints."
        )

    try:
        _generate_via_dallinger()
    except ImportError:
        _generate_via_uv(requirements_path)


def _generate_via_dallinger() -> None:
    """Use Dallinger's constraints machinery (requires experiment extra)."""
    from dallinger.constraints import generate_constraints

    generate_constraints()


def _generate_via_uv(requirements_path: Path) -> None:
    """Use ``uv pip compile`` and embed the requirements MD5 in the output."""
    if shutil.which("uv") is None:
        raise click.ClickException(
            "Could not find 'uv' on PATH. Install it with 'pip install uv' "
            "and try again, or install 'psynet[experiment]' to use the full "
            "Dallinger constraints generator."
        )

    constraints_path = Path("constraints.txt")
    req_md5 = md5(requirements_path.read_bytes()).hexdigest()
    custom_header = (
        f"psynet generate-constraints\n"
        f"#\n"
        f"# Compiled from requirements.txt with md5sum {req_md5}"
    )

    try:
        subprocess.run(
            [
                "uv",
                "pip",
                "compile",
                str(requirements_path),
                "--output-file",
                str(constraints_path),
            ],
            check=True,
            env={
                **__import__("os").environ,
                "UV_CUSTOM_COMPILE_COMMAND": custom_header,
            },
        )
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            f"Failed to compile constraints.txt via 'uv pip compile' (exit code {exc.returncode})."
        ) from exc

    # Ensure the MD5 appears in the file so _check_constraints accepts it.
    content = constraints_path.read_text()
    if req_md5 not in content:
        with open(constraints_path, "a") as f:
            f.write(f"\n# md5sum {req_md5}\n")
