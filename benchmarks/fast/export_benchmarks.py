"""Benchmarks for local PsyNet export performance.

These classes use ASV ``track_*`` methods, which record a single scalar and do
not get timed-benchmark warmup. ``asv continuous --split`` can reverse BASE and
HEAD between rounds, so a cold first I/O sample is not comparable across
commits.

``LocalAssetExport`` sets ``PSYNET_ASSET_CACHE_ROOT`` to an isolated directory,
discards a warmup export, and records a later run.
``IncrementalAssetTransfer`` already reports cold vs warm application-cache
times; it also discards one transfer first so rsync startup and OS page-cache
effects are not charged to whichever commit ran first.
"""

from __future__ import annotations

import csv
import hashlib
import json
import inspect
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEMO_RELATIVE_PATH = Path("tests/experiments/static_big")


@dataclass(frozen=True)
class _ExportProfile:
    """Configuration for one reproducible local export benchmark."""

    n_bots: int
    expected_table_rows: tuple[tuple[str, int], ...]


_EXPORT_PROFILES = {
    "static_big_single_bot": _ExportProfile(
        n_bots=1,
        expected_table_rows=(
            ("trial", 4),
            ("participant", 1),
            ("request", 11),
            ("response", 5),
            ("network", 2_000),
            ("node", 2_000),
        ),
    ),
}


@dataclass(frozen=True)
class _AssetExportProfile:
    """Configuration for one deterministic asset-export benchmark."""

    file_count: int
    file_size_bytes: int
    key_prefix: str


_ASSET_EXPORT_PROFILES = {
    "many_small_files": _AssetExportProfile(
        file_count=10_000,
        file_size_bytes=1_024,
        key_prefix="small",
    ),
    "few_large_files": _AssetExportProfile(
        file_count=10,
        file_size_bytes=10 * 1024 * 1024,
        key_prefix="large",
    ),
}


def _canonical_export_supported() -> bool:
    """Return whether the installed PsyNet can run these export benchmarks.

    ASV compares the current tree against a merge-base install. Older commits
    have no ``psynet.export`` package and a different ``export_assets()``
    signature, so the benchmark must skip rather than import removed APIs.
    """
    try:
        from psynet.data import export_assets
        from psynet.export.client import hydrate_assets
    except ImportError:
        return False
    params = inspect.signature(export_assets).parameters
    return "collected_assets_only" in params and callable(hydrate_assets)


def _skip_unless_canonical_export_supported() -> None:
    """Skip this benchmark when the compared revision predates the API.

    ASV only treats ``NotImplementedError`` as a skip when it is raised from
    ``setup``. Raised from ``setup_cache`` it aborts the whole run, so classes
    below must call this from ``setup`` and let ``setup_cache`` return ``None``.

    When that cache is ``None``, ASV calls ``setup(profile)`` with no results
    dict. ``profile`` is therefore optional on these ``setup`` methods. A
    successful run still receives ``setup(results, profile)``.
    """
    if not _canonical_export_supported():
        raise NotImplementedError("Installed PsyNet predates the canonical export API.")


def _export_benchmark_cache(builder) -> Optional[dict]:
    """Build a benchmark cache, or return None on revisions without the API."""
    if not _canonical_export_supported():
        return None
    return builder()


def _repo_root() -> Path:
    """Return the PsyNet repository root."""
    return Path(__file__).parents[2]


def _demo_dir() -> Path:
    """Return the shared benchmark experiment directory."""

    return _repo_root() / _DEMO_RELATIVE_PATH


def _benchmark_env() -> dict[str, str]:
    """Return environment variables shared by benchmark subprocesses."""

    env = os.environ.copy()
    env.setdefault("SKIP_DEPENDENCY_CHECK", "1")
    env.setdefault("BROWSER", "true")
    return env


def _run_checked(command: list[str], *, cwd: Path) -> None:
    """Run a benchmark subprocess, raising if it fails."""

    subprocess.run(command, cwd=cwd, env=_benchmark_env(), check=True)


def _populate_local_experiment(n_bots: int = 1) -> None:
    """Run an exact number of serial bots to create benchmark data."""

    _run_checked(
        [
            "psynet",
            "test",
            "local",
            "--n-bots",
            str(n_bots),
            "--serial",
            "--time-factor",
            "0",
        ],
        cwd=_demo_dir(),
    )


def _time_local_export(export_path: Path) -> float:
    """Run the canonical local export and return elapsed seconds."""

    started_at = time.perf_counter()
    _run_checked(
        [
            "psynet",
            "export",
            "local",
            "--assets",
            "none",
            "--path",
            str(export_path),
        ],
        cwd=_demo_dir(),
    )
    return time.perf_counter() - started_at


def _count_csv_rows(path: Path) -> int:
    """Count data rows in a CSV file, excluding the header row."""

    with path.open(newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


def _database_table_row_counts(export_path: Path) -> dict[str, int]:
    """Return exported row counts keyed by physical table name."""

    import zipfile

    counts: dict[str, int] = {}
    database_dir = export_path / "database"
    if database_dir.is_dir():
        for member in sorted(database_dir.glob("*.csv")):
            counts[member.stem] = _count_csv_rows(member)
        return counts

    database_zip = export_path / "database.zip"
    if not database_zip.is_file():
        return counts

    with zipfile.ZipFile(database_zip, "r") as archive:
        for member in archive.namelist():
            if not member.endswith(".csv"):
                continue
            if not (member.startswith("data/") or member.startswith("database/")):
                continue
            table = Path(member).stem
            with archive.open(member) as handle:
                text = handle.read().decode("utf-8").splitlines()
                reader = csv.reader(text)
                next(reader, None)
                counts[table] = sum(1 for _ in reader)
    return counts


def _summarize_export(
    export_path: Path,
    export_time_s: float,
    expected_table_rows: tuple[tuple[str, int], ...],
) -> dict[str, float | int]:
    """Summarize the files created by a canonical export."""

    table_row_counts = _database_table_row_counts(export_path)
    expected = dict(expected_table_rows)
    actual = {table: table_row_counts.get(table, 0) for table in expected}
    if actual != expected:
        raise RuntimeError(
            "Export benchmark fixture shape changed. "
            f"Expected table rows {expected}, got {actual}. "
            "Update the fixture expectations and benchmark version if intentional."
        )

    database_dir = export_path / "database"
    if database_dir.is_dir():
        database_size_bytes = sum(
            path.stat().st_size for path in database_dir.rglob("*") if path.is_file()
        )
    else:
        database_size_bytes = (export_path / "database.zip").stat().st_size

    return {
        "export_time_s": export_time_s,
        "data_csv_count": len(table_row_counts),
        "data_row_count": sum(table_row_counts.values()),
        "database_size_bytes": database_size_bytes,
    }


def _run_local_export_benchmark(profile: _ExportProfile) -> dict[str, float | int]:
    """Populate a local experiment, export it, and return performance metrics."""

    with tempfile.TemporaryDirectory(prefix="psynet-export-benchmark-") as export_dir:
        export_path = Path(export_dir)
        _populate_local_experiment(profile.n_bots)
        export_time_s = _time_local_export(export_path)
        return _summarize_export(
            export_path, export_time_s, profile.expected_table_rows
        )


def _deterministic_bytes(key: str, size_bytes: int) -> bytes:
    """Return deterministic binary payload for one benchmark asset."""

    block = hashlib.sha256(key.encode()).digest()
    repeats = (size_bytes + len(block) - 1) // len(block)
    return (block * repeats)[:size_bytes]


def _write_asset_payloads(
    input_dir: Path, profile: _AssetExportProfile
) -> list[dict[str, str | int]]:
    """Write benchmark asset inputs and return their manifest."""

    manifest = []
    width = max(3, len(str(profile.file_count - 1)))
    for index in range(profile.file_count):
        key = f"{profile.key_prefix}_{index:0{width}d}"
        payload = _deterministic_bytes(key, profile.file_size_bytes)
        input_path = input_dir / f"{key}.bin"
        input_path.write_bytes(payload)
        export_path = f"asset_benchmark/{key}.bin"
        manifest.append(
            {
                "key": key,
                "input_path": str(input_path),
                "export_path": export_path,
                "size_bytes": profile.file_size_bytes,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return manifest


def _run_asset_worker(
    manifest_path: Path,
    export_path: Path,
    storage_root: Path,
    result_path: Path,
) -> float:
    """Run asset deposit and export in a fresh Python process."""

    _run_checked(
        [
            "python",
            str(Path(__file__).with_name("export_benchmark_worker.py")),
            str(manifest_path),
            str(export_path),
            str(storage_root),
            str(result_path),
        ],
        cwd=_demo_dir(),
    )
    return json.loads(result_path.read_text())["asset_export_time_s"]


def _summarize_asset_export(
    export_path: Path,
    export_time_s: float,
    manifest: list[dict[str, str | int]],
) -> dict[str, float | int]:
    """Validate and summarize exported benchmark assets."""

    assets_root = export_path / "assets"
    if not assets_root.is_dir():
        assets_root = export_path

    exported_files = []
    for item in manifest:
        path = assets_root / str(item["export_path"])
        if not path.is_file():
            raise RuntimeError(
                "Asset export benchmark fixture shape changed. "
                f"Missing exported file {path}."
            )
        exported_files.append(path)
        payload = path.read_bytes()
        if len(payload) != item["size_bytes"]:
            raise RuntimeError(
                f"Unexpected size for {path}: "
                f"expected {item['size_bytes']}, got {len(payload)}."
            )
        if hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Unexpected SHA-256 digest for {path}.")

    return {
        "asset_export_time_s": export_time_s,
        "asset_file_count": len(exported_files),
        "asset_total_bytes": sum(path.stat().st_size for path in exported_files),
    }


def _run_asset_export_benchmark(
    profile: _AssetExportProfile,
) -> dict[str, float | int]:
    """Deposit deterministic assets, export them with a warmup, and return metrics."""

    with (
        tempfile.TemporaryDirectory(prefix="psynet-asset-inputs-") as input_dir,
        tempfile.TemporaryDirectory(prefix="psynet-asset-export-") as export_dir,
        tempfile.TemporaryDirectory(prefix="psynet-asset-storage-") as storage_dir,
    ):
        input_dir = Path(input_dir)
        export_path = Path(export_dir)
        storage_root = Path(storage_dir)

        _populate_local_experiment()
        manifest = _write_asset_payloads(input_dir, profile)
        manifest_path = input_dir / "manifest.json"
        result_path = input_dir / "result.json"
        manifest_path.write_text(json.dumps(manifest))
        asset_export_time_s = _run_asset_worker(
            manifest_path, export_path, storage_root, result_path
        )
        return _summarize_asset_export(export_path, asset_export_time_s, manifest)


class LocalExport:
    """Benchmark the canonical local export after a reproducible population run."""

    params = list(_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 3

    def setup_cache(self):
        """Run each export profile once and cache scalar metrics."""
        return _export_benchmark_cache(
            lambda: {
                name: _run_local_export_benchmark(profile)
                for name, profile in _EXPORT_PROFILES.items()
            }
        )

    def setup(self, results, profile=None):
        """Prepare one parameterized run.

        ``profile`` is optional because ASV omits it from the call when
        ``setup_cache`` returned ``None``; see
        ``_skip_unless_canonical_export_supported``.
        """
        _skip_unless_canonical_export_supported()

    def track_export_time_s(self, results, profile):
        """Return wall time for the local export command."""

        return results[profile]["export_time_s"]

    track_export_time_s.unit = "s"
    track_export_time_s.pretty_name = "Local export time"

    def track_data_row_count(self, results, profile):
        """Return the number of table rows written under ``database/``."""

        return results[profile]["data_row_count"]

    track_data_row_count.unit = "rows"
    track_data_row_count.pretty_name = "Local export rows"

    def track_database_size_bytes(self, results, profile):
        """Return the size of the exported table CSVs."""

        return results[profile]["database_size_bytes"]

    track_database_size_bytes.unit = "bytes"
    track_database_size_bytes.pretty_name = "Local export database size"


def _iter_incremental_assets(profile: _AssetExportProfile):
    """Yield ``(key, payload, digest)`` for one incremental-transfer profile."""
    width = max(3, len(str(profile.file_count - 1)))
    for index in range(profile.file_count):
        key = f"{profile.key_prefix}_{index:0{width}d}"
        payload = _deterministic_bytes(key, profile.file_size_bytes)
        digest = hashlib.sha256(payload).hexdigest()
        yield key, payload, digest


def _write_incremental_remote_store(
    remote_root: Path, profile: _AssetExportProfile
) -> list[tuple[str, str]]:
    """Write remote objects once and return ``(key, digest)`` for manifests."""
    objects = remote_root / "objects" / "sha256"
    objects.mkdir(parents=True, exist_ok=True)
    entries = []
    for key, payload, digest in _iter_incremental_assets(profile):
        (objects / digest).write_bytes(payload)
        entries.append((key, digest))
    return entries


def _write_incremental_export_manifest(
    export_dir: Path, entries: list[tuple[str, str]]
) -> None:
    """Write a manifest-only export tree that points at existing remote objects."""
    assets = export_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "type",
        "export_path",
        "sha256_contents",
        "is_folder",
        "storage",
    ]
    with (assets / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, (key, digest) in enumerate(entries):
            writer.writerow(
                {
                    "id": index,
                    "type": "experiment_asset",
                    "export_path": f"asset_benchmark/{key}.bin",
                    "sha256_contents": digest,
                    "is_folder": "False",
                    "storage": "LocalStorage",
                }
            )


def _hydrate_export(
    export_dir: Path,
    remote_root: Path,
    cache_root: Path,
    profile: _AssetExportProfile,
) -> float:
    """Hydrate one export tree and return elapsed seconds."""
    from psynet.export.client import hydrate_assets, plan_asset_transfer

    plan = plan_asset_transfer(str(export_dir))
    started_at = time.perf_counter()
    materialized = hydrate_assets(
        str(export_dir),
        plan,
        rsync_source=str(remote_root),
        cache_root=cache_root,
    )
    elapsed = time.perf_counter() - started_at
    if materialized != profile.file_count:
        raise RuntimeError(
            "Incremental transfer benchmark fixture shape changed. "
            f"Expected {profile.file_count} assets, got {materialized}."
        )
    return elapsed


def _run_incremental_transfer_benchmark(
    profile: _AssetExportProfile,
) -> dict[str, float | int]:
    """Time a cold and then a warm incremental asset transfer into an export tree.

    One discarded hydrate runs first so rsync startup and OS page-cache fill are
    not attributed to whichever commit ``asv continuous`` measured first. The
    timed cold run still uses an empty application cache.
    """

    with (
        tempfile.TemporaryDirectory(prefix="psynet-incremental-remote-") as remote_dir,
        tempfile.TemporaryDirectory(prefix="psynet-incremental-cache-") as cache_dir,
        tempfile.TemporaryDirectory(prefix="psynet-incremental-export-") as export_root,
    ):
        remote_root = Path(remote_dir)
        cache_root = Path(cache_dir)
        discard_export = Path(export_root) / "discard"
        cold_export = Path(export_root) / "cold"
        warm_export = Path(export_root) / "warm"

        entries = _write_incremental_remote_store(remote_root, profile)
        for export_dir in (discard_export, cold_export, warm_export):
            _write_incremental_export_manifest(export_dir, entries)
        _hydrate_export(
            discard_export, remote_root, Path(export_root) / "discard-cache", profile
        )

        return {
            "cold_transfer_time_s": _hydrate_export(
                cold_export, remote_root, cache_root, profile
            ),
            "warm_transfer_time_s": _hydrate_export(
                warm_export, remote_root, cache_root, profile
            ),
            "asset_file_count": profile.file_count,
        }


class IncrementalAssetTransfer:
    """Benchmark client-side incremental asset transfer with a cold and warm cache."""

    params = list(_ASSET_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 2

    def setup_cache(self):
        """Run each transfer profile after a discarded hydrate and cache scalars."""
        return _export_benchmark_cache(
            lambda: {
                name: _run_incremental_transfer_benchmark(profile)
                for name, profile in _ASSET_EXPORT_PROFILES.items()
            }
        )

    def setup(self, results, profile=None):
        """Prepare one parameterized run.

        ``profile`` is optional because ASV omits it from the call when
        ``setup_cache`` returned ``None``; see
        ``_skip_unless_canonical_export_supported``.
        """
        _skip_unless_canonical_export_supported()

    def track_cold_transfer_time_s(self, results, profile):
        """Return wall time to hydrate an export with an empty asset cache."""

        return results[profile]["cold_transfer_time_s"]

    track_cold_transfer_time_s.unit = "s"
    track_cold_transfer_time_s.pretty_name = "Incremental transfer time (cold cache)"

    def track_warm_transfer_time_s(self, results, profile):
        """Return wall time to hydrate an export whose objects are already cached."""

        return results[profile]["warm_transfer_time_s"]

    track_warm_transfer_time_s.unit = "s"
    track_warm_transfer_time_s.pretty_name = "Incremental transfer time (warm cache)"


class LocalAssetExport:
    """Benchmark local export of deterministic ExperimentAsset files."""

    params = list(_ASSET_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 2

    def setup_cache(self):
        """Run each asset-export profile after a warmup export and cache scalars."""
        return _export_benchmark_cache(
            lambda: {
                name: _run_asset_export_benchmark(profile)
                for name, profile in _ASSET_EXPORT_PROFILES.items()
            }
        )

    def setup(self, results, profile=None):
        """Prepare one parameterized run.

        ``profile`` is optional because ASV omits it from the call when
        ``setup_cache`` returned ``None``; see
        ``_skip_unless_canonical_export_supported``.
        """
        _skip_unless_canonical_export_supported()

    def track_asset_export_time_s(self, results, profile):
        """Return wall time for a cache-warmed local asset export."""

        return results[profile]["asset_export_time_s"]

    track_asset_export_time_s.unit = "s"
    track_asset_export_time_s.pretty_name = "Local asset export time"

    def track_asset_file_count(self, results, profile):
        """Return the number of files exported by the asset benchmark."""

        return results[profile]["asset_file_count"]

    track_asset_file_count.unit = "files"
    track_asset_file_count.pretty_name = "Local asset export files"

    def track_asset_total_bytes(self, results, profile):
        """Return total bytes exported by the asset benchmark."""

        return results[profile]["asset_total_bytes"]

    track_asset_total_bytes.unit = "bytes"
    track_asset_total_bytes.pretty_name = "Local asset export bytes"
