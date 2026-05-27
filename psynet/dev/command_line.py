"""Click commands for `psynet dev`.

These commands are part of the installed package but only function from a
PsyNet source checkout, where `CHANGELOG.md` and `changelog.d/` are present.
"""

import click

from psynet.dev import changelog as changelog_module

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
