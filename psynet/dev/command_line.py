"""Click commands for `psynet dev`.

These commands are part of the installed package but only function from a
PsyNet source checkout, where `CHANGELOG.md` and `changelog.d/` are present.
"""

import click

from psynet.dev import changelog as changelog_module
from psynet.dev import ci as ci_module
from psynet.dev import experiments as experiments_module
from psynet.dev import page_preview as page_preview_module

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


def assert_changelog_available() -> None:
    """Fail fast when not running from a PsyNet source checkout."""
    if (
        not changelog_module.CHANGELOG_PATH.exists()
        or not changelog_module.FRAGMENTS_DIR.exists()
    ):
        raise click.UsageError(
            "Run from a PsyNet source checkout: "
            f"{changelog_module.CHANGELOG_PATH} and {changelog_module.FRAGMENTS_DIR} "
            "must exist in the current directory."
        )


@click.group("dev")
def dev():
    """Developer utilities for PsyNet source checkouts."""


@dev.group("ci")
def ci():
    """Maintain CI build inputs from a PsyNet source checkout."""


@ci.command("update-dallinger-constraints")
@click.option(
    "--skip-compile-check",
    is_flag=True,
    help="Refresh the snapshot without validating Docker constraints compilation.",
)
def update_dallinger_constraints(skip_compile_check):
    """Refresh the vendored Dallinger dev-requirements snapshot."""
    ci_module.update_dallinger_constraints_command(check_compile=not skip_compile_check)


@dev.group("experiments")
def experiments():
    """Manage bundled demo and test experiments from a PsyNet source checkout."""


@dev.command("preview-page")
@click.argument("page_factory", metavar="MODULE:ATTRIBUTE")
def preview_page(page_factory):
    """Preview a page factory in a minimal one-page debug experiment."""
    try:
        page_preview_module.parse_page_target(page_factory)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    from psynet.command_line import _run_local, debug
    from psynet.utils import working_directory

    with page_preview_module.preview_experiment_directory(page_factory) as preview_dir:
        click.echo(f"Previewing {page_factory} from {preview_dir}.")
        with working_directory(preview_dir):
            _run_local(
                ctx=None,
                docker=False,
                archive=None,
                legacy=False,
                no_browsers=False,
                mode="debug",
                context_group=debug,
            )


@experiments.command("update")
@click.option(
    "--jobs",
    "n_jobs",
    default=8,
    show_default=True,
    type=int,
    help="Number of parallel jobs to use when updating experiments.",
)
@click.option(
    "--skip-constraints",
    is_flag=True,
    help="Update experiment files without regenerating constraints.txt files.",
)
def update_experiments(n_jobs, skip_constraints):
    """Update bundled demo and test experiment files."""
    try:
        experiments_module.update_command(
            n_jobs=n_jobs,
            skip_constraints_=True if skip_constraints else None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@dev.group("changelog")
def changelog():
    """Manage changelog fragments from a PsyNet source checkout."""


@changelog.command("preview")
def changelog_preview():
    """Preview rendered changelog fragments without changing files."""
    assert_changelog_available()
    try:
        changelog_module.build_command()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@changelog.command("check-mr", hidden=True)
@click.argument("base", metavar="BASE")
@click.argument("head", metavar="HEAD")
def changelog_check_mr(base, head):
    """Validate changelog requirements for a merge-request diff."""
    assert_changelog_available()
    try:
        changelog_module.check_mr_command(base, head)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@changelog.command("new")
@click.argument("category", type=click.Choice(CHANGELOG_CATEGORIES), metavar="CATEGORY")
@click.argument("description")
def changelog_new(category, description):
    """Create a new date-prefixed changelog fragment.

    CATEGORY must be one of: breaking, added, changed, deprecated, removed,
    fixed, updated, documentation.

    Example:

        psynet dev changelog new fixed "Fixed login timeout"
    """
    assert_changelog_available()
    try:
        changelog_module.new_command(category, description)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@changelog.command("release")
@click.argument("version", metavar="VERSION")
@click.argument("date", metavar="DATE")
def changelog_release(version, date):
    """Create a release section from current fragments.

    VERSION is the PsyNet release version. DATE should use YYYY-MM-DD format.

    Example:

        psynet dev changelog release 13.2.0 2026-05-18
    """
    assert_changelog_available()
    try:
        changelog_module.release_command(version, date)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
