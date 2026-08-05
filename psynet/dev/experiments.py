"""Update PsyNet's canonical standalone-experiment templates.

Historically this rewrote PsyNet Docker image tags in scaffold helpers. Constraints
locking now uses ``uv run`` of Dallinger's standalone script, and the experiment
``Dockerfile`` no longer pins a PsyNet image tag, so this command is a no-op
kept for CLI compatibility.
"""

from pathlib import Path

import click

from psynet.utils import get_psynet_root


def update_command() -> int:
    """Report that experiment-template version rewrites are no longer needed.

    Returns
    -------
    int
        Always ``0``.
    """
    assert_running_from_source_checkout_root()
    click.echo(
        "No experiment-template updates required "
        "(constraints locking uses uv run; scaffold Dockerfiles do not pin "
        "a PsyNet image tag)."
    )
    return 0


def assert_running_from_source_checkout_root() -> None:
    """Fail fast when not running from the PsyNet source checkout root."""
    if Path.cwd().resolve() != get_psynet_root().resolve():
        raise ValueError(
            "This command must be run from the PsyNet source checkout root directory."
        )
