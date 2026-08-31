"""Helpers for serving pregenerated media from the experiment ``static/`` directory.

Put public audio, images, and video in ``static/`` and pass the returned
``/static/...`` URL to prompts. Assets remain the right tool for recordings
and other files created during the experiment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


def static_url_for(
    path: Union[str, Path],
    *,
    experiment_root: Union[str, Path, None] = None,
) -> str:
    """Return the public ``/static/...`` URL for a file under ``static/``.

    Parameters
    ----------
    path
        File path, absolute or relative to the experiment directory.
    experiment_root
        Experiment directory. Defaults to the current working directory.
    """
    root = Path(experiment_root or Path.cwd()).resolve()
    static_root = (root / "static").resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    try:
        relative = resolved.relative_to(static_root)
    except ValueError as exc:
        raise ValueError(
            f"{path} is not inside {static_root}. Put pregenerated media in "
            "static/ so it can be served as /static/..., or register the file "
            "as a PsyNet asset if it is generated or lives outside the experiment."
        ) from exc
    return "/static/" + relative.as_posix()
