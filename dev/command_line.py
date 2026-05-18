"""Source-checkout-only developer commands for PsyNet."""

import importlib.util
import sys
from pathlib import Path

import click


def _load_build_changelog_module():
    script_path = Path(__file__).resolve().parent / "build_changelog.py"
    if not script_path.exists():
        raise click.ClickException(
            f"Could not find changelog builder script at {script_path}. "
            "Run this command from a PsyNet source checkout."
        )

    spec = importlib.util.spec_from_file_location("psynet_build_changelog", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@click.group("dev")
def dev():
    """Developer utilities for PsyNet source checkouts."""


@dev.command("build-changelog")
@click.option(
    "--new",
    nargs=2,
    metavar="CATEGORY DESCRIPTION",
    help=(
        "Create a new fragment file with a date-prefixed slug filename "
        "(e.g. --new fixed 'fix Selenium flake')."
    ),
)
@click.option(
    "--release",
    nargs=2,
    metavar="VERSION DATE",
    help="Create a release section from current fragments.",
)
@click.option(
    "--check-mr",
    nargs=2,
    metavar="BASE HEAD",
    help="Validate changelog fragment requirements for an MR diff.",
)
@click.pass_context
def build_changelog(ctx, new, release, check_mr):
    """Build and manage changelog fragments from a PsyNet source checkout."""
    modes = sum(1 for mode in (new, release, check_mr) if mode)
    if modes > 1:
        raise click.UsageError("Use only one of --new, --release, --check-mr.")

    module = _load_build_changelog_module()
    try:
        if new:
            category, description = new
            exit_code = module.new_command(category, description)
        elif check_mr:
            base, head = check_mr
            exit_code = module.check_mr_command(base, head)
        elif release:
            if not module.CHANGELOG_PATH.exists():
                click.echo(f"Missing {module.CHANGELOG_PATH}", err=True)
                ctx.exit(1)
            version, date = release
            exit_code = module.release_command(version, date)
        else:
            exit_code = module.build_command()
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)

    ctx.exit(exit_code)
