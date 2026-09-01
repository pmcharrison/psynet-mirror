"""Deprecated export engine: download the raw database and rebuild locally.

Why this module exists
----------------------
Before PsyNet built exports on the server, ``psynet export`` downloaded
Dallinger's raw table CSVs, **dropped and recreated the local Postgres
database**, ingested the downloaded rows into it, and then ran the export
against that local copy. That design is retained here for one release as
``--legacy``, purely as an escape hatch in case the canonical server-built
export cannot be produced for some deployment.

It is isolated in its own module for two reasons:

* It is destructive. :func:`populate_db_from_zip_file` wipes the developer's
  local database. Nothing outside this module may call it.
* It executes local experiment code and local SQLAlchemy models against remote
  data, so it needs strict local/remote dependency agreement — a constraint the
  canonical builder deliberately does not have.

Only the *ingest* half is legacy: once the remote rows are in the local
database, this module builds the export with the canonical
:func:`psynet.export.service.build_export_tree`, so an archive produced with
``--legacy`` has the same layout and contents as any other.

Do not add features here. New behaviour belongs in
:mod:`psynet.export.service` (server side) and :mod:`psynet.export.client`
(client side).
"""

from __future__ import annotations

import os
import shutil
import tempfile

from psynet.utils import get_logger, working_directory

logger = get_logger()


def download_raw_database_zip(ctx, app, docker_ssh, server, dns_host) -> str:
    """Download a remote deployment's raw database as a Dallinger CSV zip.

    Returns a temporary file path that the caller must delete.
    """
    from dallinger import data as dallinger_data
    from dallinger import db as dallinger_db

    if app is None:
        raise ValueError("An app name is required when downloading a remote database.")

    fd, database_zip_path = tempfile.mkstemp(suffix="-raw-database.zip")
    os.close(fd)
    logger.info("Downloading raw database content to %s.", database_zip_path)

    # Dallinger hard-codes the list of table names, but this list becomes out of
    # date if we add custom tables, so we have to patch it.
    dallinger_data.table_names = sorted(dallinger_db.Base.metadata.tables.keys())

    try:
        with tempfile.TemporaryDirectory() as tempdir:
            with working_directory(tempdir):
                if docker_ssh:
                    from dallinger.command_line.docker_ssh import export

                    ctx.invoke(export, server=server, app=app, no_scrub=True)
                else:
                    from dallinger.command_line import export

                    ctx.invoke(export, app=app, local=False, no_scrub=True)

                shutil.move(
                    os.path.join(tempdir, "data", f"{app}-data.zip"),
                    database_zip_path,
                )
    except Exception:
        if os.path.exists(database_zip_path):
            os.unlink(database_zip_path)
        raise

    return database_zip_path


def build_export_locally(
    ctx,
    app,
    local: bool,
    export_path: str,
    assets: str,
    docker_ssh: bool = False,
    server=None,
    dns_host=None,
) -> str:
    """Rebuild an export in ``export_path`` using the local database.

    For a remote deployment this first replaces the contents of the local
    database with the deployment's data.
    """
    from psynet.data import populate_db_from_zip_file

    from .client import fetch_logs
    from .service import build_export_tree

    if not local:
        raw_zip = None
        try:
            raw_zip = download_raw_database_zip(ctx, app, docker_ssh, server, dns_host)
            logger.info("Populating the local database with the downloaded data.")
            populate_db_from_zip_file(raw_zip)
        finally:
            if raw_zip and os.path.exists(raw_zip):
                os.unlink(raw_zip)

    build_export_tree(
        export_path,
        assets=assets,
        server=server if docker_ssh else None,
        local=local,
    )

    if docker_ssh and server:
        fetch_logs(export_path, app=app, server=server)

    return export_path
