"""Bootstrap-safe utility helpers for PsyNet.

This module provides a small set of utilities that can be imported without
triggering the heavy dependency chain (dallinger, flask, sqlalchemy, etc.)
that ``psynet.utils`` pulls in. It is used by ``psynet.bootstrap_cli``,
``psynet.experiment_setup``, and ``psynet.experiment_scaffold`` so those
modules remain importable when only the minimal ``psynet`` package (without
the ``[experiment]`` extra) is installed.

All symbols exposed here are also re-exported from ``psynet.utils`` for
backwards compatibility. Code that already imports from ``psynet.utils``
continues to work unchanged.

Design constraints
------------------
- **Stdlib only** (plus ``click`` for the error class and ``pathlib``).
  Never import dallinger, flask, sqlalchemy, or other heavy deps here.
- Keep the module small; only add helpers that are genuinely needed in
  bootstrap paths.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Union


class ExperimentDirectoryNameError(ValueError):
    """Raised when an experiment directory name collides with a non-package module."""


# ---------------------------------------------------------------------------
# MD5 directory hashing
# (copied from psynet.utils to avoid importing that module in bootstrap paths)
# ---------------------------------------------------------------------------


def _md5_update_from_file(filename: Union[str, Path], hash_obj) -> None:
    """Update *hash_obj* with the contents of *filename*."""
    if not Path(filename).is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    with open(str(filename), "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)


def _md5_update_from_dir(directory: Union[str, Path], hash_obj) -> None:
    """Recursively update *hash_obj* with all files under *directory*."""
    assert Path(directory).is_dir()
    for path in sorted(Path(directory).iterdir(), key=lambda p: str(p).lower()):
        if path.name.startswith("."):
            continue
        hash_obj.update(path.name.encode())
        if path.is_file():
            _md5_update_from_file(path, hash_obj)
        elif path.is_dir():
            _md5_update_from_dir(path, hash_obj)


def md5_directory(directory: Union[str, Path]) -> str:
    """Return the MD5 hex digest of all non-hidden files under *directory*."""
    h = hashlib.md5()
    _md5_update_from_dir(directory, h)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# PsyNet root and in-repo experiment detection
# ---------------------------------------------------------------------------


def get_psynet_root() -> Path:
    """Return the root directory of the PsyNet checkout or installed package."""
    import psynet

    return Path(psynet.__file__).parent.parent


_IN_REPO_EXPERIMENT_ROOTS = (
    "demos",
    "tests/experiments",
    "tests/playwright/experiments",
    "tests/manual_recruiter_testing",
)


def is_in_repo_experiment(path=".", *, roots=None) -> bool:
    """Return whether *path* is a PsyNet in-repo experiment (demo or test).

    In-repo experiments use the shared development environment and omit
    checked-in scaffold/constraints files; local/CI flows auto-prepare
    ignored boilerplate.

    Parameters
    ----------
    path :
        Experiment directory to check.
    roots :
        Optional iterable of in-repo roots relative to the PsyNet checkout.
        Defaults to :data:`_IN_REPO_EXPERIMENT_ROOTS`. Pass ``("demos",)``
        to restrict to bundled demos only.
    """
    path = Path(path).resolve()
    if not (path / "experiment.py").is_file():
        return False
    root = get_psynet_root().resolve()
    relative_roots = _IN_REPO_EXPERIMENT_ROOTS if roots is None else roots
    return any(
        path.is_relative_to((root / relative).resolve()) for relative in relative_roots
    )


# ---------------------------------------------------------------------------
# Experiment directory name conflict detection
# ---------------------------------------------------------------------------


def ensure_experiment_directory_name_does_not_conflict(path=".") -> None:
    """Check that the experiment directory basename is safe for Dallinger imports.

    Dallinger imports a local experiment as ``<directory_name>.experiment``.
    A directory named like an existing non-package module, for example
    ``code``, can resolve to the standard library module instead of the
    local experiment directory.

    Parameters
    ----------
    path : str or Path, optional
        Path to the experiment directory.

    Raises
    ------
    ExperimentDirectoryNameError
        If Python resolves the directory name to an unrelated non-package module.
    """
    path = Path(path).resolve()
    module_name = path.name
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ExperimentDirectoryNameError(
            f"The current experiment directory is named '{module_name}', which "
            "Python cannot import as a top-level package. Dallinger imports "
            "experiments by directory name, so it cannot import this experiment "
            "reliably. Rename the directory to a valid top-level package name."
        ) from exc
    if spec is None:
        return
    # A package resolution can still support ``<name>.experiment``. The
    # problematic case is a plain module such as the standard-library
    # ``code.py``, which has no submodule search path and cannot contain
    # ``code.experiment``.
    if spec.submodule_search_locations is not None:
        return

    candidate_paths = []
    if spec.origin not in (None, "built-in"):
        candidate_paths.append(Path(spec.origin))

    # If Python resolves the name back into the experiment directory, the
    # import machinery will see the local experiment rather than an unrelated
    # module.
    if any(
        candidate_path.resolve().is_relative_to(path)
        for candidate_path in candidate_paths
    ):
        return

    module_path = spec.origin if spec.origin is not None else module_name
    raise ExperimentDirectoryNameError(
        f"The current experiment directory is named '{module_name}', but Python's "
        f"module '{module_name}' resolves to '{module_path}' instead of "
        "this directory. Dallinger imports experiments by directory name, so it "
        "cannot import this experiment reliably. Rename the directory or move the "
        "runnable experiment into a nested non-conflicting directory, for example "
        f"'{module_name}/<experiment_slug>/'."
    )
