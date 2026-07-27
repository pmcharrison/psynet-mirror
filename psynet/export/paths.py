"""Export archive path resolution.

Export packaging uses a single product (``export.zip`` / extracted export
directory) with table CSVs under ``database/``. Archive ingestion and analysis
helpers accept three equivalent inputs:

* an ``export.zip`` file;
* a ``database/`` directory of table CSVs;
* an extracted export directory that contains ``database/``.

Legacy zips that store members as ``data/<table>.csv`` (old ``database.zip``)
are still accepted for ``--archive`` and analysis.
"""

from __future__ import annotations

import os
import zipfile
from typing import Optional

DATABASE_DIRNAME = "database"
EXPORT_ZIP_NAME = "export.zip"


def is_zip_path(path: str) -> bool:
    """Return whether ``path`` looks like a zip archive."""
    return os.path.isfile(path) and path.lower().endswith(".zip")


def resolve_database_dir(path: str) -> str:
    """Resolve ``path`` to a directory containing ``<table>.csv`` files.

    Parameters
    ----------
    path :
        An ``export.zip``, a ``database/`` directory, or an extracted export
        directory that contains ``database/``.

    Returns
    -------
    str
        Absolute path to the directory of table CSVs.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If ``path`` is an ``export.zip`` (use :func:`iter_table_csv_members`
        / zip-aware loaders) or the layout cannot be resolved on disk.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    if is_zip_path(path):
        raise ValueError(
            f"{path} is a zip archive; use zip-aware loaders rather than "
            "resolve_database_dir."
        )

    if os.path.isdir(path):
        nested = os.path.join(path, DATABASE_DIRNAME)
        if os.path.isdir(nested) and _dir_has_csv(nested):
            return nested
        if _dir_has_csv(path):
            return path
        raise ValueError(
            f"Could not find table CSVs at {path} or {nested}. "
            "Pass export.zip, a database/ directory, or an extracted export "
            "directory containing database/."
        )

    raise ValueError(f"Unsupported archive path: {path}")


def _dir_has_csv(directory: str) -> bool:
    try:
        return any(name.endswith(".csv") for name in os.listdir(directory))
    except OSError:
        return False


def table_csv_path(database_dir: str, table: str) -> str:
    """Return ``database_dir/<table>.csv``."""
    return os.path.join(database_dir, f"{table}.csv")


def find_table_member_in_zip(archive: zipfile.ZipFile, table: str) -> Optional[str]:
    """Return the zip member path for ``table``, or ``None``.

    Prefers ``database/<table>.csv``, then legacy ``data/<table>.csv``.
    """
    candidates = [
        f"{DATABASE_DIRNAME}/{table}.csv",
        f"data/{table}.csv",
    ]
    names = set(archive.namelist())
    for candidate in candidates:
        if candidate in names:
            return candidate
    # Tolerate accidental absolute-style or prefixed members.
    suffix_new = f"/{DATABASE_DIRNAME}/{table}.csv"
    suffix_legacy = f"/data/{table}.csv"
    matches = [
        name
        for name in names
        if name.endswith(f"{DATABASE_DIRNAME}/{table}.csv")
        or name.endswith(f"data/{table}.csv")
        or name.endswith(suffix_new)
        or name.endswith(suffix_legacy)
    ]
    # Prefer exact database/ over data/ when both somehow match.
    for preferred in candidates:
        for name in matches:
            if name.endswith(preferred):
                return name
    return matches[0] if matches else None


def list_table_names_in_zip(archive: zipfile.ZipFile) -> list[str]:
    """Return table names discovered in a zip archive."""
    tables = []
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        base = os.path.basename(name)
        if not base.endswith(".csv"):
            continue
        parent = os.path.basename(os.path.dirname(name))
        if parent in (DATABASE_DIRNAME, "data"):
            tables.append(base[: -len(".csv")])
    # Prefer database/ names if both layouts somehow appear.
    return sorted(set(tables))
