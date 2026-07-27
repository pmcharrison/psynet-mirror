"""Prepare experiment directories and synchronize their virtual environments.

This module holds the non-Click orchestration used by ``psynet setup`` and
``psynet scripts scaffold``: virtualenv checks, shared-checkout sync gating,
editable PsyNet requirement selection, and scaffold/constraint preparation.
Click commands stay in ``command_line`` and call into these helpers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from .experiment_scaffold import (
    commit_psynet_requirement,
    editable_psynet_requirement,
    get_editable_psynet_source,
    get_psynet_requirement,
    pin_unpinned_psynet_requirement,
    scaffold_experiment_directory,
    set_psynet_requirement,
)
from .utils import (
    ExperimentDirectoryNameError,
    ensure_experiment_directory_name_does_not_conflict,
    get_psynet_root,
    is_in_repo_experiment,
)


def _assert_directory_is_scaffoldable():
    """Block scaffolding only when the directory name conflicts with a Python module."""
    try:
        ensure_experiment_directory_name_does_not_conflict()
    except ExperimentDirectoryNameError as exc:
        raise click.UsageError(str(exc)) from exc


def _generate_constraints_if_missing(ctx, *, requirements_changed=False):
    """Generate a non-empty constraints file when scaffolding needs one."""
    constraints_path = Path("constraints.txt")
    if constraints_path.exists() and not constraints_path.is_file():
        raise click.UsageError("constraints.txt exists but is not a regular file.")
    if (
        not requirements_changed
        and constraints_path.is_file()
        and constraints_path.stat().st_size > 0
    ):
        return

    click.echo("Generating constraints.txt...")
    # Lazy import avoids a circular import with command_line at module load.
    from .command_line import generate_constraints

    ctx.invoke(generate_constraints)
    if not constraints_path.is_file() or constraints_path.stat().st_size == 0:
        raise click.ClickException(
            "Failed to generate a non-empty constraints.txt file."
        )


def _scaffold_experiment(ctx, *, skip_constraints, refresh_constraints=False):
    """Scaffold an experiment and optionally prepare its constraints.

    In-repo experiments (demos and test experiments) keep bare ``psynet``
    requirements and omit constraints by design, so pinning and constraint
    generation are skipped there even without ``--skip-constraints``.
    """
    _assert_directory_is_scaffoldable()
    if is_in_repo_experiment():
        skip_constraints = True
    scaffold_result = scaffold_experiment_directory()
    if not skip_constraints:
        requirements_changed = (
            "requirements.txt" in scaffold_result["written"]
            or pin_unpinned_psynet_requirement()
        )
        _generate_constraints_if_missing(
            ctx,
            requirements_changed=requirements_changed or refresh_constraints,
        )


def _ensure_active_virtualenv():
    """Require setup to run inside an active virtual environment."""
    if sys.prefix == sys.base_prefix and not os.environ.get("VIRTUAL_ENV"):
        raise click.UsageError(
            "PsyNet setup must run in an active virtual environment. "
            "Create one with 'uv venv --python 3.13', then activate it before "
            "trying again."
        )


def _run_uv(args, description):
    """Run one uv command and report a concise Click error on failure."""
    if shutil.which("uv") is None:
        raise click.ClickException(
            "Could not find uv. Install it with 'pip install uv' and try again."
        )
    try:
        subprocess.run(["uv", *args], check=True)
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"Failed to {description}.") from exc


def _is_interactive():
    """Return whether setup can prompt for user choices."""
    return sys.stdin.isatty()


def _is_psynet_checkout_virtualenv():
    """Return whether the active interpreter is PsyNet's shared checkout ``.venv``.

    Nested virtualenvs elsewhere under the checkout (for example a demo's own
    ``.venv``) are not treated as the shared development environment.
    """
    prefix = Path(sys.prefix).resolve()
    checkout_venv = (get_psynet_root() / ".venv").resolve()
    return prefix == checkout_venv or prefix.is_relative_to(checkout_venv)


def _warn_shared_checkout_sync():
    """Emit a stern warning before syncing PsyNet's shared checkout venv."""
    click.echo(
        "Warning: synchronizing will run 'uv pip sync --strict' against this "
        "shared PsyNet development environment and can remove packages that "
        "other PsyNet work depends on.",
        err=True,
    )


def _resolve_shared_checkout_venv_action(*, prepare_only, force_shared_env):
    """Decide how setup should treat PsyNet's shared checkout virtualenv.

    Returns ``"prepare-only"`` or ``"sync"``. Raises on cancel or invalid flags.
    """
    if prepare_only and force_shared_env:
        raise click.UsageError(
            "--prepare-only and --force-shared-env cannot be used together."
        )

    in_shared_env = _is_psynet_checkout_virtualenv()
    if force_shared_env and not in_shared_env:
        raise click.UsageError(
            "--force-shared-env is only applicable when the active virtual "
            "environment is PsyNet's shared checkout environment."
        )
    if not in_shared_env:
        return "prepare-only" if prepare_only else "sync"

    if prepare_only:
        return "prepare-only"
    if force_shared_env:
        _warn_shared_checkout_sync()
        return "sync"

    if not _is_interactive():
        raise click.UsageError(
            "The active virtual environment appears to be PsyNet's shared "
            "checkout environment. Refusing to synchronize without an explicit "
            "choice. Use --prepare-only to scaffold and generate constraints "
            "without syncing, --force-shared-env to sync anyway (this can remove "
            "packages from the shared PsyNet development environment), or cancel "
            "by not running setup."
        )

    click.echo(
        "The active virtual environment appears to be PsyNet's shared checkout "
        "environment."
    )
    click.echo(
        "Choose 'cancel' to abort with no changes, 'prepare-only' to scaffold "
        "and generate constraints without syncing, or 'sync' to synchronize "
        "anyway (this can remove packages from the shared PsyNet development "
        "environment)."
    )
    choice = click.prompt(
        "Shared environment action",
        type=click.Choice(["cancel", "prepare-only", "sync"]),
        default="cancel",
    )
    if choice == "cancel":
        click.echo("Aborted setup; no experiment or environment changes were made.")
        raise click.Abort()
    if choice == "sync":
        _warn_shared_checkout_sync()
    return choice


def _editable_checkout_is_dirty(source):
    """Return whether an editable PsyNet checkout has uncommitted changes."""
    result = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _choose_editable_psynet_requirement(source, requested_source):
    """Resolve how setup should represent an active editable PsyNet checkout."""
    editable_requirement = editable_psynet_requirement(source)
    requirements_path = Path("requirements.txt")
    try:
        existing_requirement = (
            get_psynet_requirement() if requirements_path.is_file() else None
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if existing_requirement == editable_requirement and requested_source is None:
        return editable_requirement

    explicit_existing = (
        existing_requirement is not None and existing_requirement.lower() != "psynet"
    )
    choices = ["editable", "commit"]
    if explicit_existing:
        choices.append("existing")

    if requested_source is None:
        if not _is_interactive():
            options = ", ".join(f"--psynet-source {choice}" for choice in choices)
            raise click.UsageError(
                f"PsyNet is installed editable from {source}. Choose how setup "
                f"should represent it with one of: {options}."
            )
        click.echo(f"PsyNet is installed editable from {source}.")
        click.echo(
            "Choose 'editable' to include local changes, 'commit' for a portable "
            "Git pin from this checkout's origin remote, or 'existing' to retain "
            "the current requirements entry."
        )
        requested_source = click.prompt(
            "PsyNet source",
            type=click.Choice(choices),
        )
    elif requested_source not in choices:
        raise click.UsageError(
            f"--psynet-source {requested_source} is unavailable for this experiment."
        )

    if requested_source == "editable":
        return editable_requirement
    if requested_source == "existing":
        return existing_requirement

    try:
        requirement = commit_psynet_requirement(source)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if _editable_checkout_is_dirty(source):
        click.echo(
            "Warning: the commit pin excludes uncommitted changes in the editable "
            "PsyNet checkout.",
            err=True,
        )
    return requirement


def setup_experiment(ctx, *, psynet_source, prepare_only, force_shared_env):
    """Scaffold and synchronize an experiment's dedicated virtual environment."""
    if is_in_repo_experiment():
        _scaffold_experiment(ctx, skip_constraints=True)
        click.echo(
            "Prepared in-repo experiment using PsyNet's shared development environment."
        )
        return

    _ensure_active_virtualenv()
    action = _resolve_shared_checkout_venv_action(
        prepare_only=prepare_only,
        force_shared_env=force_shared_env,
    )

    editable_source = get_editable_psynet_source()
    if editable_source is None:
        if psynet_source is not None:
            raise click.UsageError(
                "--psynet-source is only needed when PsyNet is installed editable."
            )
        _scaffold_experiment(
            ctx,
            skip_constraints=False,
            refresh_constraints=True,
        )
    else:
        requirement = _choose_editable_psynet_requirement(
            editable_source,
            psynet_source,
        )
        _scaffold_experiment(ctx, skip_constraints=True)
        set_psynet_requirement(requirement)
        _generate_constraints_if_missing(ctx, requirements_changed=True)

    if action == "prepare-only":
        click.echo("Prepared experiment files without synchronizing dependencies.")
        return

    _run_uv(
        [
            "pip",
            "sync",
            "constraints.txt",
            "--strict",
        ],
        "synchronize experiment dependencies",
    )
    _run_uv(["pip", "check"], "verify experiment dependencies")
