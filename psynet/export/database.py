"""COPY-based database table export into a flat ``database/`` directory."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Iterable, Optional

import psycopg2
from dallinger import db
from psycopg2 import sql
from sqlalchemy import inspect as sa_inspect

from psynet.utils import get_logger, make_parents, sha256_file

from .identifiers import (
    apply_identifier_separation_to_csv_dir,
    write_identifier_sidecars_from_csv_dir,
)
from .paths import DATABASE_DIRNAME, find_table_member_in_zip, is_zip_path

logger = get_logger()


def _export_table_order() -> list[str]:
    """Return physical table names in a stable export order."""
    inspector = sa_inspect(db.engine)
    names = sorted(inspector.get_table_names())
    preferred = [
        "network",
        "participant",
        "response",
        "node",
        "info",
        "trial",
        "notification",
        "question",
        "transformation",
        "vector",
        "transmission",
        "asset",
        "lucid_rid",
        "lucid_status",
        "request",
        "error",
        "process",
    ]
    ordered = [name for name in preferred if name in names]
    ordered.extend(name for name in names if name not in ordered)
    return ordered


def _db_dsn() -> str:
    return db.db_url


def copy_database_to_csv_dir(
    csv_dir: str, table_names: Optional[Iterable[str]] = None
) -> list[str]:
    """Copy each physical table to ``csv_dir/<table>.csv`` via PostgreSQL COPY.

    Returns
    -------
    list[str]
        Table names that were exported (including empty tables).
    """
    os.makedirs(csv_dir, exist_ok=True)
    tables = list(table_names) if table_names is not None else _export_table_order()
    conn = psycopg2.connect(dsn=_db_dsn())
    try:
        cur = conn.cursor()
        for table in tables:
            path = os.path.join(csv_dir, f"{table}.csv")
            with open(path, "w", newline="") as handle:
                query = sql.SQL("COPY {} TO STDOUT WITH CSV HEADER").format(
                    sql.Identifier(table)
                )
                cur.copy_expert(query, handle)
    finally:
        conn.close()
    return tables


def _count_csv_rows(path: str) -> int:
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _file_entry(path: str) -> dict:
    return {"sha256": sha256_file(path), "bytes": os.path.getsize(path)}


def _provenance_for_manifest() -> dict:
    """Return deployment, experiment label, and git provenance for ``manifest.json``.

    ``experiment_label`` lets a client verify after the fact that an export came
    from the experiment it thinks it did, without querying the experiment
    database separately.
    """
    provenance = {
        "deployment_id": None,
        "experiment_label": None,
        "git_commit_sha": None,
        "git_dirty": None,
    }
    try:
        from psynet.experiment import get_experiment

        experiment = get_experiment()
        provenance["deployment_id"] = experiment.deployment_id
        provenance["experiment_label"] = experiment.label
        provenance["git_commit_sha"] = experiment.var.get("git_commit_sha", None)
        provenance["git_dirty"] = experiment.var.get("git_dirty", None)
        return provenance
    except Exception:
        logger.warning(
            "Could not resolve experiment git provenance for export manifest.",
            exc_info=True,
        )
    try:
        from psynet import deployment_info

        if deployment_info.is_available():
            provenance["git_commit_sha"] = deployment_info.read("git_commit_sha")
            provenance["git_dirty"] = deployment_info.read("git_dirty")
    except Exception:
        logger.warning(
            "Could not read deployment_info git provenance for export manifest.",
            exc_info=True,
        )
    return provenance


def write_export_manifest(
    export_path: str,
    *,
    table_names: list[str],
    csv_dir: str,
    extra_files: Optional[dict[str, str]] = None,
) -> str:
    """Write ``manifest.json`` describing the export.

    The manifest records ``git_commit_sha`` and ``git_dirty`` from launch
    provenance. Exports do not bundle experiment source code.
    """
    from psynet import __version__ as psynet_version

    try:
        from dallinger.version import __version__ as dallinger_version
    except Exception:
        logger.warning(
            "Could not determine the Dallinger version for the export manifest.",
            exc_info=True,
        )
        dallinger_version = None

    row_counts = {}
    files = {}
    for table in table_names:
        path = os.path.join(csv_dir, f"{table}.csv")
        if os.path.exists(path):
            row_counts[table] = _count_csv_rows(path)
            files[f"{DATABASE_DIRNAME}/{table}.csv"] = _file_entry(path)

    if extra_files:
        for name, path in extra_files.items():
            if os.path.exists(path):
                files[name] = _file_entry(path)

    from .service import EXPORT_FORMAT_VERSION

    provenance = _provenance_for_manifest()

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "export_format_version": EXPORT_FORMAT_VERSION,
        "deployment_id": provenance["deployment_id"],
        "experiment_label": provenance["experiment_label"],
        "git_commit_sha": provenance["git_commit_sha"],
        "git_dirty": provenance["git_dirty"],
        "psynet_version": psynet_version,
        "dallinger_version": dallinger_version,
        "table_row_counts": row_counts,
        "files": files,
        "identifier_separation": True,
    }
    manifest_path = os.path.join(export_path, "manifest.json")
    with open(make_parents(manifest_path), "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest_path


def export_database_snapshot(export_path: str) -> dict:
    """Export pseudonymous table CSVs plus identifier sidecars.

    Parameters
    ----------
    export_path :
        Directory that will receive ``database/``, identifier CSVs, and
        ``manifest.json``.

    Returns
    -------
    dict
        Paths to the written artifacts.
    """
    os.makedirs(export_path, exist_ok=True)
    database_dir = os.path.join(export_path, DATABASE_DIRNAME)
    if os.path.exists(database_dir):
        shutil.rmtree(database_dir)

    with tempfile.TemporaryDirectory() as tempdir:
        raw_dir = os.path.join(tempdir, "raw")
        separated_dir = os.path.join(tempdir, "separated")
        table_names = copy_database_to_csv_dir(raw_dir)

        sidecar_paths = write_identifier_sidecars_from_csv_dir(raw_dir, export_path)
        apply_identifier_separation_to_csv_dir(raw_dir, separated_dir, table_names)
        shutil.copytree(separated_dir, database_dir)

        manifest_path = write_export_manifest(
            export_path,
            table_names=table_names,
            csv_dir=database_dir,
            extra_files=sidecar_paths,
        )

    return {
        "database_dir": database_dir,
        "manifest": manifest_path,
        **sidecar_paths,
    }


def load_zip_table_to_stringio(archive_path: str, table: str) -> io.StringIO:
    """Return a text buffer for ``table`` from an export or legacy zip."""
    if not is_zip_path(archive_path):
        raise ValueError(f"Expected a zip archive, got {archive_path}")
    with zipfile.ZipFile(archive_path, "r") as archive:
        member = find_table_member_in_zip(archive, table)
        if member is None:
            raise KeyError(f"Table CSV for {table!r} not found in {archive_path}")
        with archive.open(member) as handle:
            return io.StringIO(handle.read().decode("utf-8"))
