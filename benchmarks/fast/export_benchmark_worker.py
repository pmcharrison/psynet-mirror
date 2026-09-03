"""Isolated worker for the local asset-export benchmark.

Asset setup imports experiment-local SQLAlchemy models and mutates deployment
state, so each ASV profile runs this worker in a fresh process. The parent
benchmark prepares deterministic input files and validates the exported output;
this module only deposits those files and times the asset export operation.

The timed sample is a warmed ``export_assets`` call. ASV ``track_*`` methods
have no warmup, and ``asv continuous`` interleaves rounds by default, so it
can measure HEAD before BASE. A single cold export would fill the shared
content-addressed cache for whichever commit ran second. Each worker therefore
sets ``PSYNET_ASSET_CACHE_ROOT`` to a temporary directory and discards the
first export.
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import sys
import time
from contextlib import contextmanager
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


@contextmanager
def _temporary_default_asset_cache(cache_root: Path):
    """Point ``export_assets`` at an isolated cache for the duration of the block.

    The default cache at ``~/psynet-data/cache/assets`` is content-addressed by
    SHA-256. These benchmarks use deterministic payloads, so a first commit
    would otherwise donate cache hits to the second commit in ``asv continuous``.
    """
    previous = os.environ.get("PSYNET_ASSET_CACHE_ROOT")
    os.environ["PSYNET_ASSET_CACHE_ROOT"] = str(Path(cache_root).expanduser())
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PSYNET_ASSET_CACHE_ROOT", None)
        else:
            os.environ["PSYNET_ASSET_CACHE_ROOT"] = previous


def _export_collected_assets(assets_dir: Path) -> None:
    """Write collected local assets into ``assets_dir``."""
    from psynet.data import export_assets

    assets_dir.mkdir(parents=True, exist_ok=True)
    export_assets(
        str(assets_dir),
        collected_assets_only=True,
        include_on_demand_assets=False,
        local=True,
    )


def _time_warmed_asset_export(assets_dir: Path) -> float:
    """Export once to warm caches, then time a second export into ``assets_dir``.

    The warmup destination is a sibling of ``assets_dir`` so the timed run still
    creates a fresh export tree. Warmup files are deleted afterwards; the
    isolated object cache from the first export remains for the timed run.
    """
    warmup_dir = assets_dir.with_name(f"{assets_dir.name}.warmup")
    try:
        _export_collected_assets(warmup_dir)
    finally:
        shutil.rmtree(warmup_dir, ignore_errors=True)
    started_at = time.perf_counter()
    _export_collected_assets(assets_dir)
    return time.perf_counter() - started_at


def run(
    manifest_path: Path,
    export_path: Path,
    storage_root: Path,
    result_path: Path,
) -> None:
    """Deposit manifest assets and time a cache-warmed local export."""

    from dallinger import db

    from psynet.asset import ExperimentAsset, LocalStorage
    from psynet.data import export_assets

    params = inspect.signature(export_assets).parameters
    if "collected_assets_only" not in params:
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

    assets_dir = export_path / "assets"
    with _temporary_default_asset_cache(storage_root / "export-asset-cache"):
        elapsed = _time_warmed_asset_export(assets_dir)
    result_path.write_text(json.dumps({"asset_export_time_s": elapsed}))


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
