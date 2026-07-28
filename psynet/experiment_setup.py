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

    When constraints are enabled, an existing bare ``psynet`` requirement is
    pinned before template files are written so a failed pin does not leave a
    half-complete scaffold.
    """
    _assert_directory_is_scaffoldable()
    if is_in_repo_experiment():
        skip_constraints = True

    pinned_existing_requirement = False
    if not skip_constraints and Path("requirements.txt").is_file():
        try:
            pinned_existing_requirement = pin_unpinned_psynet_requirement()
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc

    scaffold_result = scaffold_experiment_directory()
    if not skip_constraints:
        try:
            requirements_changed = (
                "requirements.txt" in scaffold_result["written"]
                or pinned_existing_requirement
                or pin_unpinned_psynet_requirement()
            )
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
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


def _psynet_command_env_mismatch_error():
    """Return an error if the shell venv and running PsyNet disagree.

    This catches the common footgun where a user activates a new experiment
    ``.venv`` but still invokes ``psynet`` from PsyNet's shared checkout env
    because PsyNet has not been installed into the new environment yet.
    """
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if not virtual_env:
        return None

    virtual_env_path = Path(virtual_env).resolve()
    prefix = Path(sys.prefix).resolve()
    if prefix == virtual_env_path or prefix.is_relative_to(virtual_env_path):
        return None

    install_hint = "uv pip install psynet"
    editable_source = get_editable_psynet_source()
    if editable_source is not None:
        install_hint = f"uv pip install -e {editable_source}"
    elif _is_psynet_checkout_virtualenv():
        install_hint = f"uv pip install -e {get_psynet_root()}"

    return (
        f"Your shell has VIRTUAL_ENV={virtual_env_path}, but this `psynet` "
        f"command is running from {prefix}. PsyNet is probably not installed "
        "in the activated environment yet.\n\n"
        "Finish setup with:\n"
        f"  {install_hint}\n"
        "  psynet setup\n\n"
        "If `psynet` still points at the old environment afterward, run "
        "`hash -r` or open a new shell."
    )


def _run_uv(args, description, *, quiet=False):
    """Run one uv command and report a concise Click error on failure."""
    if shutil.which("uv") is None:
        raise click.ClickException(
            "Could not find uv. Install it with 'pip install uv' and try again."
        )
    try:
        subprocess.run(
            ["uv", *args],
            check=True,
            capture_output=quiet,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = ""
        if quiet and exc.stderr:
            detail = f"\n{exc.stderr.strip()}"
        raise click.ClickException(f"Failed to {description}.{detail}") from exc


def _is_interactive():
    """Return whether setup can prompt for user choices."""
    return sys.stdin.isatty()


def _prompt_numeric_choice(title, options, *, default_index=0, intro=None):
    """Prompt for a 1-based numeric choice from ``options``.

    Parameters
    ----------
    title :
        Prompt label shown after the option list.
    options :
        Sequence of ``(value, description)`` pairs. ``value`` is returned when
        selected; ``description`` is shown to the user.
    default_index :
        Zero-based index of the default option.
    intro :
        Optional explanation printed before the numbered options.
    """
    if not options:
        raise ValueError("options must not be empty")
    if not 0 <= default_index < len(options):
        raise ValueError("default_index is out of range")

    if intro:
        click.echo(intro)
        click.echo()

    for index, (_value, description) in enumerate(options, start=1):
        marker = " (default)" if index - 1 == default_index else ""
        click.echo(f"  {index}. {description}{marker}")

    choice = click.prompt(
        title,
        type=click.IntRange(1, len(options)),
        default=default_index + 1,
    )
    return options[choice - 1][0]


def _create_dedicated_experiment_virtualenv():
    """Create ``./.venv`` for a standalone experiment and print re-run steps."""
    venv_path = Path(".venv")
    if venv_path.exists():
        raise click.UsageError(
            "A .venv directory already exists here. Activate it with "
            "'source .venv/bin/activate', install PsyNet into it, then re-run "
            "'psynet setup', or remove it first if you want setup to recreate it."
        )

    _run_uv(
        ["venv", f"--python={_recommended_python()}"],
        "create a dedicated experiment virtual environment",
        quiet=True,
    )
    click.echo("Created ./.venv.")
    click.echo()
    click.echo("Next steps (setup is not finished until you run these):")
    click.echo("  source .venv/bin/activate")
    editable_source = get_editable_psynet_source()
    if editable_source is not None:
        click.echo(f"  uv pip install -e {editable_source}")
    else:
        click.echo("  uv pip install psynet")
    click.echo("  psynet setup")


def _recommended_python():
    """Return the recommended Python major.minor for new experiment venvs."""
    from .version import recommended_python_major_minor

    return recommended_python_major_minor


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


def _resolve_shared_checkout_venv_action(*, no_install, force_shared_env):
    """Decide how setup should treat PsyNet's shared checkout virtualenv.

    Returns ``"no-install"``, ``"sync"``, ``"new-venv"``, or ``"cancel"``.
    Raises on invalid flags. ``new-venv`` means create a dedicated environment
    and stop so the user can install PsyNet into it and re-run setup.
    """
    if no_install and force_shared_env:
        raise click.UsageError(
            "--no-install and --force-shared-env cannot be used together."
        )

    in_shared_env = _is_psynet_checkout_virtualenv()
    if force_shared_env and not in_shared_env:
        raise click.UsageError(
            "--force-shared-env is only applicable when the active virtual "
            "environment is PsyNet's shared checkout environment."
        )
    if not in_shared_env:
        return "no-install" if no_install else "sync"

    if no_install:
        return "no-install"
    if force_shared_env:
        _warn_shared_checkout_sync()
        return "sync"

    if not _is_interactive():
        raise click.UsageError(
            "The active virtual environment appears to be PsyNet's shared "
            "checkout environment. Refusing to synchronize without an explicit "
            "choice. Create a dedicated environment with "
            f"'uv venv --python={_recommended_python()}', activate it, and "
            "re-run setup; or use --no-install to scaffold and generate "
            "constraints without installing packages; or use "
            "--force-shared-env to sync anyway (this can remove packages from "
            "the shared PsyNet development environment)."
        )

    choice = _prompt_numeric_choice(
        "What do you want to do?",
        [
            (
                "new-venv",
                "Create a dedicated .venv here (recommended), then install "
                "PsyNet into it and re-run setup",
            ),
            ("cancel", "Cancel — leave everything as-is"),
            (
                "no-install",
                "Write files only — scaffold/constraints, don't install packages",
            ),
            (
                "sync",
                "Install into PsyNet's shared .venv anyway "
                "(can break other PsyNet work)",
            ),
        ],
        default_index=0,
        intro=(
            "Setup for a standalone experiment should use a dedicated "
            "virtualenv in this directory. You're currently using PsyNet's "
            "development .venv from the repository checkout, so choose how "
            "to continue:"
        ),
    )
    if choice == "cancel":
        click.echo("Cancelled setup; no experiment or environment changes were made.")
        return "cancel"
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
                f"should record it in this experiment's requirements.txt with "
                f"one of: {options}."
            )
        descriptions = {
            "editable": (
                "Editable — point requirements at this local checkout "
                "(includes uncommitted changes)"
            ),
            "commit": (
                "Git commit pin — record a specific PsyNet Git commit URL "
                "(the commit must already be pushed)"
            ),
            "existing": (
                "Existing — keep the current PsyNet entry in requirements.txt"
            ),
        }
        requested_source = _prompt_numeric_choice(
            "What do you want to do?",
            [(choice, descriptions[choice]) for choice in choices],
            intro=(
                f"PsyNet is installed editable from {source}.\n"
                "How should setup record it in this experiment's "
                "requirements.txt?"
            ),
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


def _default_no_install_psynet_source():
    """Choose a non-interactive PsyNet source for no-install setup.

    Prefer retaining an explicit requirements pin; otherwise use the editable
    checkout. Bare ``psynet`` falls through to editable.
    """
    requirements_path = Path("requirements.txt")
    if not requirements_path.is_file():
        return "editable"
    try:
        existing_requirement = get_psynet_requirement()
    except ValueError:
        return "editable"
    if existing_requirement is not None and existing_requirement.lower() != "psynet":
        return "existing"
    return "editable"


def _echo_in_repo_setup_success():
    """Explain that bundled demos use the repository development environment."""
    click.echo(
        "This folder is a PsyNet bundled demo or test experiment. "
        "Prepared ignored boilerplate only; the PsyNet repository's "
        "development .venv is used on purpose, and setup does not install "
        "packages here.\n\n"
        "To make a standalone experiment, copy the folder outside the PsyNet "
        "repo, then run:\n"
        f"  uv venv --python {_recommended_python()}\n"
        "  source .venv/bin/activate\n"
        "  uv pip install psynet\n"
        "  psynet setup"
    )


def _echo_no_install_success(*, docker):
    """Print success and next steps after a files-only setup."""
    if docker:
        click.echo(
            "Prepared experiment files for Docker "
            "(scaffolded boilerplate and constraints; did not install packages "
            "into the local virtual environment).\n\n"
            "Next steps:\n"
            "  Follow the generated instructions under docker/docs."
        )
        return

    click.echo(
        "Prepared experiment files without installing packages "
        "(scaffolded boilerplate and constraints).\n\n"
        "Next steps:\n"
        "  Make sure this directory's dedicated .venv is active and PsyNet is "
        "installed in it, then run:\n"
        "  psynet setup\n"
        "  (omit --no-install / --docker so setup can install from "
        "constraints.txt)"
    )


def setup_experiment(ctx, *, psynet_source, no_install, force_shared_env, docker=False):
    """Scaffold and synchronize an experiment's dedicated virtual environment."""
    if is_in_repo_experiment():
        _scaffold_experiment(ctx, skip_constraints=True)
        _echo_in_repo_setup_success()
        return

    _ensure_active_virtualenv()
    mismatch = _psynet_command_env_mismatch_error()
    if mismatch is not None:
        raise click.UsageError(mismatch)

    action = _resolve_shared_checkout_venv_action(
        no_install=no_install,
        force_shared_env=force_shared_env,
    )
    if action == "cancel":
        return
    if action == "new-venv":
        _create_dedicated_experiment_virtualenv()
        return

    # No-install already answered the shared-env question; don't add a second
    # interactive menu. Keep an explicit pin if present, otherwise use editable.
    if (
        action == "no-install"
        and psynet_source is None
        and get_editable_psynet_source() is not None
    ):
        psynet_source = _default_no_install_psynet_source()

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

    if action == "no-install":
        _echo_no_install_success(docker=docker)
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
    click.echo("Setup complete.")
