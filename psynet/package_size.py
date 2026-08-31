"""Deployment-plan size limit for experiment packages.

The default ceiling is sized so authors can bake public audiovisual stimuli
into ``static/`` without hitting the old 256 MB tripwire. It is not a
Heroku-slug guarantee: Heroku remains capped at 500 MB. Raise
``EXP_MAX_SIZE_MB`` only after reviewing ``dallinger deployment-files list``.
"""

from __future__ import annotations

import os

DEFAULT_EXP_MAX_SIZE_MB = 1024
EXP_MAX_SIZE_MB_ENV = "EXP_MAX_SIZE_MB"
HEROKU_MAX_SLUG_MB = 500


def apply_default_exp_max_size_mb() -> None:
    """Expose PsyNet's default to Dallinger's own size check."""
    os.environ.setdefault(EXP_MAX_SIZE_MB_ENV, str(DEFAULT_EXP_MAX_SIZE_MB))


def get_exp_max_size_mb(*, heroku: bool = False) -> int:
    """Return the configured deployment-plan size limit in mebibytes.

    Reading the limit does not write ``EXP_MAX_SIZE_MB``. Call
    :func:`apply_default_exp_max_size_mb` during runtime init so Dallinger
    sees the same default.
    """
    raw = os.environ.get(EXP_MAX_SIZE_MB_ENV)
    configured = DEFAULT_EXP_MAX_SIZE_MB if raw is None else int(raw)
    if heroku:
        return min(configured, HEROKU_MAX_SLUG_MB)
    return configured


def package_size_limit_error(
    size_in_mb: float, max_size_in_mb: int, *, heroku: bool = False
) -> str:
    """Build the error shown when an experiment package is too large."""
    if heroku:
        return (
            f"Your experiment deployment plan is {size_in_mb:.1f} MB, which "
            f"exceeds Heroku's {HEROKU_MAX_SLUG_MB} MB slug limit. Run "
            "'dallinger deployment-files list' and exclude files in "
            "deploy.toml, host large public media on S3, or deploy with "
            "Docker/SSH."
        )
    return (
        f"Your experiment deployment plan is {size_in_mb:.1f} MB, which exceeds "
        f"the {max_size_in_mb} MB limit. The default "
        f"{DEFAULT_EXP_MAX_SIZE_MB} MB ceiling is meant for baking public "
        "stimuli into static/. Run 'dallinger deployment-files list' to see "
        "what is included, then exclude junk in deploy.toml. If the size is "
        f"intentional, set {EXP_MAX_SIZE_MB_ENV} to override this limit. Do "
        "not use that override to ship generated files, recordings, or private "
        "data; those belong in PsyNet's asset system. Heroku slugs cannot "
        f"exceed {HEROKU_MAX_SLUG_MB} MB, so host large media outside the "
        "package or deploy with Docker/SSH."
    )
