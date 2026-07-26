"""Benchmarks for local PsyNet export performance."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _ExportProfile:
    """Configuration for one reproducible local export benchmark."""

    demo_root: str
    demo_name: str
    n_bots: int
    expected_csv_rows: tuple[tuple[str, int], ...]
    assets: str = "none"
    anonymize: str = "no"


_EXPORT_PROFILES = {
    "static_big_single_bot": _ExportProfile(
        demo_root="tests/experiments",
        demo_name="static_big",
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
class _AssetFileSpec:
    """One deterministic file in the asset-export benchmark workload."""

    key: str
    size_bytes: int


@dataclass(frozen=True)
class _AssetExportProfile:
    """Configuration for one deterministic asset-export benchmark."""

    demo_root: str
    demo_name: str
    files: tuple[_AssetFileSpec, ...]


_ASSET_EXPORT_PROFILES = {
    "mixed_local_assets": _AssetExportProfile(
        demo_root="tests/experiments",
        demo_name="static_big",
        files=(
            *(
                _AssetFileSpec(key=f"small_{index:03d}", size_bytes=1_024)
                for index in range(24)
            ),
            *(
                _AssetFileSpec(key=f"large_{index:03d}", size_bytes=256 * 1_024)
                for index in range(3)
            ),
        ),
    ),
}


def _repo_root() -> Path:
    """Return the PsyNet repository root."""

    return Path(__file__).parents[2]


def _benchmark_env() -> dict[str, str]:
    """Return environment variables shared by benchmark subprocesses."""

    env = os.environ.copy()
    env.setdefault("SKIP_DEPENDENCY_CHECK", "1")
    env.setdefault("BROWSER", "true")
    return env


def _run_checked(command: list[str], *, cwd: Path) -> None:
    """Run a benchmark subprocess, raising if it fails."""

    subprocess.run(command, cwd=cwd, env=_benchmark_env(), check=True)


def _populate_local_experiment(demo_dir: Path, profile: _ExportProfile) -> None:
    """Run an exact number of serial bots to create benchmark data."""

    _run_checked(
        [
            "psynet",
            "test",
            "local",
            "--n-bots",
            str(profile.n_bots),
            "--serial",
            "--time-factor",
            "0",
        ],
        cwd=demo_dir,
    )


def _time_local_export(demo_dir: Path, export_path: Path, profile: _ExportProfile) -> float:
    """Run the local legacy export and return elapsed seconds."""

    started_at = time.perf_counter()
    _run_checked(
        [
            "psynet",
            "export",
            "local",
            "--legacy",
            "--assets",
            profile.assets,
            "--anonymize",
            profile.anonymize,
            "--no-source",
            "--path",
            str(export_path),
        ],
        cwd=demo_dir,
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

    demo_dir = _repo_root() / profile.demo_root / profile.demo_name
    with tempfile.TemporaryDirectory(prefix="psynet-export-benchmark-") as export_dir:
        export_path = Path(export_dir)
        _populate_local_experiment(demo_dir, profile)
        export_time_s = _time_local_export(demo_dir, export_path, profile)
        return _summarize_export(
            export_path, export_time_s, profile.expected_csv_rows
        )


def _deterministic_bytes(key: str, size_bytes: int) -> bytes:
    """Return deterministic binary payload for one benchmark asset."""

    random_source = random.Random(key)
    return random_source.randbytes(size_bytes)


def _write_asset_payloads(
    input_dir: Path, profile: _AssetExportProfile
) -> list[dict[str, str | int]]:
    """Write benchmark asset inputs and return their manifest."""

    manifest = []
    for spec in profile.files:
        payload = _deterministic_bytes(spec.key, spec.size_bytes)
        input_path = input_dir / f"{spec.key}.bin"
        input_path.write_bytes(payload)
        export_path = f"asset_benchmark/{spec.key}.bin"
        manifest.append(
            {
                "key": spec.key,
                "input_path": str(input_path),
                "export_path": export_path,
                "size_bytes": spec.size_bytes,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return manifest


def _deposit_experiment_assets(demo_dir: Path, manifest: list[dict[str, str | int]]):
    """Deposit benchmark assets through PsyNet's ExperimentAsset API."""

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file:
        json.dump(manifest, file)
        manifest_path = file.name

    script = """
import json
import sys
from pathlib import Path

from dallinger import db
from psynet.asset import ExperimentAsset

manifest = json.loads(Path(sys.argv[1]).read_text())
for item in manifest:
    asset = ExperimentAsset(
        input_path=item["input_path"],
        key_within_experiment=f"asset_benchmark/{item['key']}",
        extension=".bin",
        personal=False,
        obfuscate=0,
    )
    asset.deposit()
db.session.commit()
"""
    try:
        _run_checked(["python", "-c", script, manifest_path], cwd=demo_dir)
    finally:
        Path(manifest_path).unlink(missing_ok=True)


def _time_asset_export(demo_dir: Path, export_path: Path) -> float:
    """Run asset-only local export and return elapsed seconds."""

    script = """
import sys
import time
from pathlib import Path

from psynet.data import export_assets

started_at = time.perf_counter()
export_assets(
    Path(sys.argv[1]),
    include_private=True,
    experiment_assets_only=True,
    include_on_demand_assets=False,
    local=True,
)
print(time.perf_counter() - started_at)
"""
    started = subprocess.run(
        ["python", "-c", script, str(export_path)],
        cwd=demo_dir,
        env=_benchmark_env(),
        check=True,
        text=True,
        capture_output=True,
    )
    return float(started.stdout.strip().splitlines()[-1])


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

    demo_dir = _repo_root() / profile.demo_root / profile.demo_name
    with tempfile.TemporaryDirectory(prefix="psynet-asset-inputs-") as input_dir:
        with tempfile.TemporaryDirectory(prefix="psynet-asset-export-") as export_dir:
            _populate_local_experiment(
                demo_dir,
                _ExportProfile(
                    demo_root=profile.demo_root,
                    demo_name=profile.demo_name,
                    n_bots=1,
                    expected_csv_rows=(),
                ),
            )
            manifest = _write_asset_payloads(Path(input_dir), profile)
            _deposit_experiment_assets(demo_dir, manifest)
            export_path = Path(export_dir)
            asset_export_time_s = _time_asset_export(demo_dir, export_path)
            return _summarize_asset_export(
                export_path, asset_export_time_s, manifest
            )


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
