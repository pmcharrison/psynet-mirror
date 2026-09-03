"""Isolated worker for the local asset-export benchmark.

Asset setup imports experiment-local SQLAlchemy models and mutates deployment
state, so each ASV profile runs this worker in a fresh process. The parent
benchmark prepares deterministic input files and validates the exported output;
this module only deposits those files. The timed operation lives in
``export_benchmarks.py`` and drives the public ``psynet export local`` command.

Keep this worker setup-only. If timing logic is added here, the benchmark stops
showing the subprocess command that experiment authors actually run, and it is
harder to reason about which cache belongs to the timed export.
"""

from __future__ import annotations

import json
import sys
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
    storage_root: Path,
) -> None:
    """Deposit manifest assets for the parent benchmark to export."""

    from dallinger import db

    from psynet.asset import ExperimentAsset, LocalStorage

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


def _main() -> None:
    """Run the worker with paths supplied by the parent benchmark."""

    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: export_benchmark_worker.py <manifest> <storage-root>"
        )
    run(*(Path(value) for value in sys.argv[1:]))


if __name__ == "__main__":
    _main()
