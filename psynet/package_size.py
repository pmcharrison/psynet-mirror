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


def apply_default_exp_max_size_mb() -> None:
    """Expose PsyNet's default to Dallinger's own size check."""
    os.environ.setdefault(EXP_MAX_SIZE_MB_ENV, str(DEFAULT_EXP_MAX_SIZE_MB))


def get_exp_max_size_mb() -> int:
    """Return the configured deployment-plan size limit in mebibytes."""
    apply_default_exp_max_size_mb()
    return int(os.environ[EXP_MAX_SIZE_MB_ENV])


def package_size_limit_error(size_in_mb: float, max_size_in_mb: int) -> str:
    """Build the error shown when an experiment package is too large."""
    return (
        f"Your experiment deployment plan is {size_in_mb:.1f} MB, which exceeds "
        f"the {max_size_in_mb} MB limit. The default "
        f"{DEFAULT_EXP_MAX_SIZE_MB} MB ceiling is meant for baking public "
        "stimuli into static/. Run 'dallinger deployment-files list' to see "
        "what is included, then exclude junk in deploy.toml. If the size is "
        f"intentional, set {EXP_MAX_SIZE_MB_ENV} to override this limit. Do "
        "not use that override to ship generated files, recordings, or private "
        "data; those belong in PsyNet's asset system. Heroku slugs cannot "
        "exceed 500 MB, so host large media outside the package or deploy "
        "with Docker/SSH."
    )
