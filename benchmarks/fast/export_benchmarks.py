"""Benchmarks for local PsyNet export performance."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_DEMO_RELATIVE_PATH = Path("tests/experiments/static_big")


@dataclass(frozen=True)
class _ExportProfile:
    """Configuration for one reproducible local export benchmark."""

    n_bots: int
    expected_csv_rows: tuple[tuple[str, int], ...]


_EXPORT_PROFILES = {
    "static_big_single_bot": _ExportProfile(
        n_bots=1,
        expected_csv_rows=(
            ("AnimalTrial", 4),
            ("Bot", 1),
            ("ChainTrialMakerState", 1),
            ("ExperimentConfig", 1),
            ("Request", 11),
            ("Response", 5),
            ("StaticNetwork", 2_000),
            ("StaticNode", 2_000),
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
    """Run the local legacy export and return elapsed seconds."""

    started_at = time.perf_counter()
    _run_checked(
        [
            "psynet",
            "export",
            "local",
            "--legacy",
            "--assets",
            "none",
            "--anonymize",
            "no",
            "--no-source",
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


def _csv_row_counts(data_dir: Path) -> dict[str, int]:
    """Return exported row counts keyed by CSV filename stem."""

    return {
        path.stem: _count_csv_rows(path) for path in sorted(data_dir.glob("*.csv"))
    }


def _summarize_export(
    export_path: Path,
    export_time_s: float,
    expected_csv_rows: tuple[tuple[str, int], ...],
) -> dict[str, float | int]:
    """Summarize the files created by a legacy export."""

    data_dir = export_path / "regular" / "data"
    csv_row_counts = _csv_row_counts(data_dir)
    expected = dict(expected_csv_rows)
    if csv_row_counts != expected:
        raise RuntimeError(
            "Export benchmark fixture shape changed. "
            f"Expected CSV rows {expected}, got {csv_row_counts}. "
            "Update the fixture expectations and benchmark version if intentional."
        )

    database_zip = export_path / "regular" / "database.zip"

    return {
        "export_time_s": export_time_s,
        "data_csv_count": len(csv_row_counts),
        "data_row_count": sum(csv_row_counts.values()),
        "database_zip_size_bytes": database_zip.stat().st_size,
    }


def _run_local_export_benchmark(profile: _ExportProfile) -> dict[str, float | int]:
    """Populate a local experiment, export it, and return performance metrics."""

    with tempfile.TemporaryDirectory(prefix="psynet-export-benchmark-") as export_dir:
        export_path = Path(export_dir)
        _populate_local_experiment(profile.n_bots)
        export_time_s = _time_local_export(export_path)
        return _summarize_export(
            export_path, export_time_s, profile.expected_csv_rows
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

    exported_files = sorted(path for path in export_path.rglob("*") if path.is_file())
    expected_by_path = {str(item["export_path"]): item for item in manifest}
    actual_relative_paths = {
        str(path.relative_to(export_path)) for path in exported_files
    }
    if actual_relative_paths != set(expected_by_path):
        raise RuntimeError(
            "Asset export benchmark fixture shape changed. "
            f"Expected paths {sorted(expected_by_path)}, got {sorted(actual_relative_paths)}."
        )

    for path in exported_files:
        relative_path = str(path.relative_to(export_path))
        expected = expected_by_path[relative_path]
        payload = path.read_bytes()
        if len(payload) != expected["size_bytes"]:
            raise RuntimeError(
                f"Unexpected size for {relative_path}: "
                f"expected {expected['size_bytes']}, got {len(payload)}."
            )
        if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
            raise RuntimeError(f"Unexpected SHA-256 digest for {relative_path}.")

    return {
        "asset_export_time_s": export_time_s,
        "asset_file_count": len(exported_files),
        "asset_total_bytes": sum(path.stat().st_size for path in exported_files),
    }


def _run_asset_export_benchmark(
    profile: _AssetExportProfile,
) -> dict[str, float | int]:
    """Deposit deterministic assets, export them, and return metrics."""

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


class LegacyLocalExport:
    """Benchmark legacy local export after a small reproducible population run."""

    params = list(_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 2

    def setup_cache(self):
        """Run each export profile once and cache scalar metrics."""

        return {
            name: _run_local_export_benchmark(profile)
            for name, profile in _EXPORT_PROFILES.items()
        }

    def track_export_time_s(self, results, profile):
        """Return wall time for the legacy local export command."""

        return results[profile]["export_time_s"]

    track_export_time_s.unit = "s"
    track_export_time_s.pretty_name = "Legacy local export time"

    def track_data_row_count(self, results, profile):
        """Return the number of rows written to class-based CSV exports."""

        return results[profile]["data_row_count"]

    track_data_row_count.unit = "rows"
    track_data_row_count.pretty_name = "Legacy local export rows"

    def track_database_zip_size_bytes(self, results, profile):
        """Return the size of the raw Dallinger database snapshot."""

        return results[profile]["database_zip_size_bytes"]

    track_database_zip_size_bytes.unit = "bytes"
    track_database_zip_size_bytes.pretty_name = "Legacy local database.zip size"


class LocalAssetExport:
    """Benchmark local export of deterministic ExperimentAsset files."""

    params = list(_ASSET_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 1

    def setup_cache(self):
        """Run each asset-export profile once and cache scalar metrics."""

        return {
            name: _run_asset_export_benchmark(profile)
            for name, profile in _ASSET_EXPORT_PROFILES.items()
        }

    def track_asset_export_time_s(self, results, profile):
        """Return wall time for the local asset export phase."""

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
