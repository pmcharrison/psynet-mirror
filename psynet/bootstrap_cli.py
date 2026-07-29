"""Minimal bootstrap CLI for PsyNet.

This module provides the ``psynet`` entry point.  It is intentionally slim so
that running ``psynet setup``, ``psynet scripts …``, ``psynet services …``,
and ``psynet generate-constraints`` works with only the minimal ``psynet``
distribution (i.e. without the ``[experiment]`` extra installed).

Dispatch strategy
-----------------
The ``main()`` function inspects ``sys.argv`` to decide which CLI to run:

- If the first user-visible argument is one of the *bootstrap commands*
  (``setup``, ``scripts``, ``services``, ``generate-constraints``) **or** a
  version flag (``--version`` / ``-V``), the lightweight bootstrap group is
  invoked directly without importing experiment-runtime code.

- Otherwise (or for bare ``psynet`` / ``psynet --help``) the full heavy CLI
  in ``psynet.command_line`` is imported and invoked.  If that import fails
  with an ``ImportError`` (i.e. the ``[experiment]`` extra is not installed),
  a friendly message is printed that directs the user to run ``psynet setup``
  or install ``psynet[experiment]``.

This pattern means that bootstrap commands are always fast and never require
the experiment runtime, while full-featured experiment commands are still
available whenever the runtime is installed.
"""

from __future__ import annotations

import sys

import click

from psynet.experiment_scaffold import (
    PRUNE_FORCE_OPTION_HELP,
    PRUNE_PRESERVE_TRACKED_OPTION_HELP,
)
from psynet.version import psynet_version

_BOOTSTRAP_COMMANDS = frozenset(
    {
        "setup",
        "scripts",
        "services",
        "generate-constraints",
    }
)

_VERSION_FLAGS = frozenset({"--version", "-V"})


# ---------------------------------------------------------------------------
# Bootstrap Click group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(
    psynet_version,
    "--version",
    "-V",
    message="%(version)s",
)
def _bootstrap():
    """PsyNet bootstrap commands (available without experiment runtime)."""
    pass


# -- setup ------------------------------------------------------------------


@_bootstrap.command("setup")
@click.option(
    "--psynet-source",
    type=click.Choice(["editable", "commit", "existing"]),
    default=None,
    help="How to represent an active editable PsyNet installation.",
)
@click.option(
    "--no-install",
    is_flag=True,
    help="Scaffold and generate constraints without installing packages.",
)
@click.option(
    "--docker",
    is_flag=True,
    help=(
        "Prepare files for Docker mode (same as --no-install, with Docker "
        "next-step guidance)."
    ),
)
@click.option(
    "--force-shared-env",
    is_flag=True,
    help="Allow synchronizing PsyNet's shared checkout virtual environment.",
)
@click.pass_context
def setup(ctx, psynet_source, no_install, docker, force_shared_env):
    """Scaffold and synchronize an experiment's dedicated virtual environment."""
    if docker:
        if force_shared_env:
            raise click.UsageError(
                "--docker and --force-shared-env cannot be used together."
            )
        no_install = True
    from psynet.experiment_setup import setup_experiment

    setup_experiment(
        ctx,
        psynet_source=psynet_source,
        no_install=no_install,
        force_shared_env=force_shared_env,
        docker=docker,
    )


# -- scripts ----------------------------------------------------------------


@_bootstrap.group("scripts")
def scripts():
    """Manage experiment boilerplate scripts and templates."""
    pass


@scripts.command("scaffold")
@click.option(
    "--skip-constraints",
    is_flag=True,
    help="Do not pin PsyNet or generate constraints.txt.",
)
@click.pass_context
def scripts_scaffold(ctx, skip_constraints):
    """Create any missing PsyNet boilerplate files for the experiment directory."""
    from psynet.experiment_setup import _scaffold_experiment

    _scaffold_experiment(ctx, skip_constraints=skip_constraints)


@scripts.command("update")
@click.pass_context
def scripts_update(ctx):
    """Overwrite experiment boilerplate with the latest PsyNet templates."""
    from pathlib import Path

    from psynet.experiment_scaffold import scaffold_experiment_directory
    from psynet.light_utils import (
        ExperimentDirectoryNameError,
        ensure_experiment_directory_name_does_not_conflict,
    )

    try:
        ensure_experiment_directory_name_does_not_conflict()
    except ExperimentDirectoryNameError as e:
        raise click.UsageError(str(e))
    if not Path("experiment.py").is_file():
        raise click.UsageError(
            "The current directory is not a valid PsyNet experiment "
            "(missing experiment.py)."
        )
    scaffold_experiment_directory(overwrite=True)


@scripts.command("prune")
@click.option(
    "--force",
    is_flag=True,
    help=PRUNE_FORCE_OPTION_HELP,
)
@click.option(
    "--preserve-tracked",
    is_flag=True,
    help=PRUNE_PRESERVE_TRACKED_OPTION_HELP,
)
@click.pass_context
def scripts_prune(ctx, force, preserve_tracked):
    """Remove scaffold-managed boilerplate files from the experiment directory."""
    from psynet.experiment_scaffold import run_scripts_prune

    run_scripts_prune(force=force, preserve_tracked=preserve_tracked)


# -- services ---------------------------------------------------------------


@_bootstrap.group("services")
def services():
    """Check and ensure local PostgreSQL and Redis services."""
    pass


@services.command("check")
def services_check():
    """Verify that local PostgreSQL and Redis are reachable.

    Does not start services. Exits with an error if either is unavailable.
    """
    from psynet.services import verify_local_services

    verify_local_services(strict=True)


@services.command("ensure")
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    help="Start missing services with Docker without prompting.",
)
def services_ensure(assume_yes):
    """Ensure local PostgreSQL and Redis are reachable.

    If a service is missing, offers to start Docker containers that publish
    localhost ports 5432 and 6379.
    """
    from psynet.services import ensure_local_services

    ensure_local_services(assume_yes=assume_yes, strict=True)


# -- generate-constraints ---------------------------------------------------


@_bootstrap.command("generate-constraints")
def generate_constraints():
    """Generate the constraints.txt file from requirements.txt."""
    from psynet.constraints_compile import generate_constraints_file

    generate_constraints_file()


# ---------------------------------------------------------------------------
# Entry point dispatcher
# ---------------------------------------------------------------------------


def _first_user_arg() -> str | None:
    """Return the first non-flag argument from sys.argv (after the script name)."""
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            return arg
    return None


def _has_version_flag() -> bool:
    """Return True if sys.argv contains a version flag."""
    return bool(_VERSION_FLAGS & set(sys.argv[1:]))


def _load_full_psynet_cli():
    """Import the full experiment CLI group (requires ``[experiment]``)."""
    from psynet.command_line import psynet as _full_psynet

    return _full_psynet


def main() -> None:
    """Dispatcher: run bootstrap CLI or full experiment CLI.

    Bootstrap commands (``setup``, ``scripts``, ``services``,
    ``generate-constraints``) and version flags are handled without importing
    the experiment runtime.  Every other invocation delegates to the full
    ``psynet.command_line.psynet`` group, printing a helpful message if the
    ``[experiment]`` extra is not installed.
    """
    first = _first_user_arg()
    use_bootstrap = first in _BOOTSTRAP_COMMANDS or _has_version_flag()

    if use_bootstrap:
        _bootstrap(standalone_mode=True)
        return

    # Try loading the full experiment CLI.
    try:
        _full_psynet = _load_full_psynet_cli()
    except ImportError as exc:
        # Experiment runtime not installed.
        if first is None or first in ("--help", "-h"):
            # Show bootstrap help, note that more commands need [experiment].
            click.echo(
                "PsyNet bootstrap CLI (psynet[experiment] not installed).\n\n"
                "Available commands: setup, scripts, services, generate-constraints\n\n"
                "To access full experiment commands:\n"
                "  psynet setup          (installs psynet[experiment] via constraints)\n"
                "  uv pip install 'psynet[experiment]'\n"
            )
            _bootstrap(["--help"], standalone_mode=False)
        else:
            click.echo(
                f"Error: command '{first}' requires the full PsyNet experiment "
                "runtime, which is not installed.\n\n"
                "Install it with:\n"
                "  psynet setup\n"
                "or:\n"
                "  uv pip install 'psynet[experiment]'\n",
                err=True,
            )
            raise SystemExit(1) from exc
        return

    _full_psynet(standalone_mode=True)
