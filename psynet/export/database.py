"""PostgreSQL COPY-based database snapshot export."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Iterable, Optional

import psycopg2
from dallinger import db
from psycopg2 import sql
from sqlalchemy import inspect as sa_inspect

from psynet.utils import get_logger, make_parents

from .identifiers import (
    apply_identifier_separation_to_csv_dir,
    write_identifier_sidecars_from_csv_dir,
)

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


def copy_database_to_csv_dir(csv_dir: str, table_names: Optional[Iterable[str]] = None) -> list[str]:
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


def _zip_csv_dir(csv_dir: str, zip_path: str, table_names: list[str]) -> None:
    """Write ``data/<table>.csv`` members into ``zip_path`` without recompressing."""
    make_parents(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table in table_names:
            member = f"data/{table}.csv"
            source = os.path.join(csv_dir, f"{table}.csv")
            archive.write(source, member)


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_csv_rows(path: str) -> int:
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def write_export_manifest(
    export_path: str,
    *,
    table_names: list[str],
    csv_dir: str,
    database_zip_path: str,
    extra_files: Optional[dict[str, str]] = None,
) -> str:
    """Write ``manifest.json`` describing the snapshot."""
    from psynet import __version__ as psynet_version

    try:
        import dallinger

        dallinger_version = getattr(dallinger, "__version__", None)
    except Exception:
        dallinger_version = None

    row_counts = {}
    for table in table_names:
        path = os.path.join(csv_dir, f"{table}.csv")
        if os.path.exists(path):
            row_counts[table] = _count_csv_rows(path)

    files = {
        "database.zip": {
            "sha256": _file_sha256(database_zip_path),
            "bytes": os.path.getsize(database_zip_path),
        }
    }
    if extra_files:
        for name, path in extra_files.items():
            if os.path.exists(path):
                files[name] = {
                    "sha256": _file_sha256(path),
                    "bytes": os.path.getsize(path),
                }

    deployment_id = None
    try:
        from psynet.experiment import get_experiment

        deployment_id = get_experiment().deployment_id
    except Exception:
        logger.debug("Could not resolve deployment_id for export manifest.", exc_info=True)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment_id": deployment_id,
        "psynet_version": psynet_version,
        "dallinger_version": dallinger_version,
        "table_row_counts": row_counts,
        "files": files,
        "identifier_separation": True,
        "anonymous": False,
    }
    manifest_path = os.path.join(export_path, "manifest.json")
    with open(make_parents(manifest_path), "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest_path


def export_database_snapshot(export_path: str) -> dict:
    """Export a pseudonymous ``database.zip`` plus identifier sidecars.

    Parameters
    ----------
    export_path :
        Directory that will receive ``database.zip``, identifier CSVs, and
        ``manifest.json``.

    Returns
    -------
    dict
        Paths to the written artifacts.
    """
    os.makedirs(export_path, exist_ok=True)
    database_zip_path = os.path.join(export_path, "database.zip")

    with tempfile.TemporaryDirectory() as tempdir:
        raw_dir = os.path.join(tempdir, "raw")
        separated_dir = os.path.join(tempdir, "separated")
        table_names = copy_database_to_csv_dir(raw_dir)

        sidecar_paths = write_identifier_sidecars_from_csv_dir(raw_dir, export_path)
        apply_identifier_separation_to_csv_dir(raw_dir, separated_dir, table_names)
        _zip_csv_dir(separated_dir, database_zip_path, table_names)

        manifest_path = write_export_manifest(
            export_path,
            table_names=table_names,
            csv_dir=separated_dir,
            database_zip_path=database_zip_path,
            extra_files=sidecar_paths,
        )

    return {
        "database_zip": database_zip_path,
        "manifest": manifest_path,
        **sidecar_paths,
    }


def load_zip_table_to_stringio(database_zip: str, table: str) -> io.StringIO:
    """Return a text buffer for ``data/<table>.csv`` inside a database zip."""
    member = f"data/{table}.csv"
    with zipfile.ZipFile(database_zip, "r") as archive:
        with archive.open(member) as handle:
            return io.StringIO(handle.read().decode("utf-8"))
