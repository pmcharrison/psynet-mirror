"""Benchmarks for local PsyNet export performance."""

from __future__ import annotations

import csv
import os
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
