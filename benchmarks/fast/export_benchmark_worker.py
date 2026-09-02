"""Isolated worker for the local asset-export benchmark.

Asset setup imports experiment-local SQLAlchemy models and mutates deployment
state, so each ASV profile runs this worker in a fresh process. The parent
benchmark prepares deterministic input files and validates the exported output;
this module only deposits those files and times the asset export operation.
"""

import inspect
import json
import sys
import time
from pathlib import Path


def _initialize_experiment() -> None:
    """Initialize experiment models and deployment state."""

    from psynet import deployment_info
    from psynet.command_line import _experiment_variables, db_connection
    from psynet.experiment import import_local_experiment

    with db_connection("local") as connection:
        experiment_vars = _experiment_variables(connection)
    deployment_info.init(
        redeploying_from_archive=False,
        mode="debug",
        is_local_deployment=True,
        is_ssh_deployment=False,
        server=None,
        app=None,
    )
    deployment_info.write(deployment_id=experiment_vars["deployment_id"])
    import_local_experiment()


def run(
    manifest_path: Path,
    export_path: Path,
    storage_root: Path,
    result_path: Path,
) -> None:
    """Deposit manifest assets and time their local export."""

    from dallinger import db

    from psynet.asset import ExperimentAsset, LocalStorage
    from psynet.data import export_assets

    params = inspect.signature(export_assets).parameters
    if "manifest_only" not in params:
        raise NotImplementedError(
            "Installed PsyNet predates the canonical export_assets() signature."
        )

    _initialize_experiment()
    storage = LocalStorage(root=str(storage_root))
    manifest = json.loads(manifest_path.read_text())
    for item in manifest:
        asset = ExperimentAsset(
            input_path=item["input_path"],
            key_within_experiment=f"asset_benchmark/{item['key']}",
            extension=".bin",
        )
        asset.deposit(storage=storage)
    db.session.commit()

    started_at = time.perf_counter()
    assets_dir = export_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    export_assets(
        str(assets_dir),
        local=True,
    )
    result_path.write_text(
        json.dumps({"asset_export_time_s": time.perf_counter() - started_at})
    )


def _main() -> None:
    """Run the worker with paths supplied by the parent benchmark."""

    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: export_benchmark_worker.py "
            "<manifest> <export-path> <storage-root> <result>"
        )
    run(*(Path(value) for value in sys.argv[1:]))


if __name__ == "__main__":
    _main()
