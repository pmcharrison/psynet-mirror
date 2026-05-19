"""Source-checkout-only developer commands for PsyNet."""

import importlib.util
import sys
from pathlib import Path

import click


def _load_changelog_module():
    script_path = Path(__file__).resolve().parent / "changelog.py"
    if not script_path.exists():
        raise click.ClickException(
            f"Could not find changelog builder script at {script_path}. "
            "Run this command from a PsyNet source checkout."
        )

    spec = importlib.util.spec_from_file_location("psynet_changelog", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_update_demos_module():
    script_path = Path(__file__).resolve().parents[1] / "demos" / "update_demos.py"
    if not script_path.exists():
        raise click.ClickException(
            f"Could not find demo updater script at {script_path}. "
            "Run this command from a PsyNet source checkout."
        )

    spec = importlib.util.spec_from_file_location("psynet_update_demos", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@click.group("dev")
def dev():
    """Developer utilities for PsyNet source checkouts."""


@dev.command("update-demos")
@click.option(
    "--jobs",
    "n_jobs",
    default=8,
    show_default=True,
    type=int,
    help="Number of parallel jobs to use when updating demos.",
)
@click.option(
    "--skip-constraints",
    is_flag=True,
    help="Update demo files without regenerating constraints.txt files.",
)
@click.pass_context
def update_demos(ctx, n_jobs, skip_constraints):
    """Update bundled demo files from the current PsyNet source checkout."""
    module = _load_update_demos_module()
    try:
        exit_code = module.main(
            n_jobs=n_jobs,
            skip_constraints_=True if skip_constraints else None,
        )
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)

    ctx.exit(exit_code)


@dev.group("changelog")
def changelog():
    """Manage changelog fragments from a PsyNet source checkout."""


@changelog.command("preview")
@click.pass_context
def changelog_preview(ctx):
    """Preview rendered changelog fragments without changing files."""
    module = _load_changelog_module()
    try:
        exit_code = module.build_command()
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)

    ctx.exit(exit_code)


CHANGELOG_CATEGORIES = (
    "breaking",
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "updated",
    "documentation",
)


@changelog.command("new")
@click.argument("category", type=click.Choice(CHANGELOG_CATEGORIES), metavar="CATEGORY")
@click.argument("description")
@click.pass_context
def changelog_new(ctx, category, description):
    """Create a new date-prefixed changelog fragment.

    CATEGORY must be one of: breaking, added, changed, deprecated, removed,
    fixed, updated, documentation.

    Example:

        psynet dev changelog new fixed "Fixed login timeout"
    """
    module = _load_changelog_module()
    try:
        exit_code = module.new_command(category, description)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)

    ctx.exit(exit_code)


@changelog.command("release")
@click.argument("version", metavar="VERSION")
@click.argument("date", metavar="DATE")
@click.pass_context
def changelog_release(ctx, version, date):
    """Create a release section from current fragments.

    VERSION is the PsyNet release version. DATE should use YYYY-MM-DD format.

    Example:

        psynet dev changelog release 13.2.0 2026-05-18
    """
    module = _load_changelog_module()
    try:
        if not module.CHANGELOG_PATH.exists():
            click.echo(f"Missing {module.CHANGELOG_PATH}", err=True)
            ctx.exit(1)
        exit_code = module.release_command(version, date)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)

    ctx.exit(exit_code)
