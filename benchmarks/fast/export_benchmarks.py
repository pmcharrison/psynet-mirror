"""Benchmarks for local PsyNet export performance.

ASV ``time_*`` methods measure elapsed export time. Each benchmark's
``setup(profile)`` prepares and validates one profile, and ``teardown(profile)``
removes its temporary files. The asset benchmark warms an isolated
content-addressed cache before timed runs: ``asv continuous`` interleaves rounds
by default, so BASE and HEAD can run in either order and a cold first I/O sample
is not comparable across commits.

There are two export benchmarks in this module:

``LocalExport``
    Populates the ``static_big`` demo and measures ``psynet export local
    --assets none``. This is the database-only export baseline.

``LocalAssetExport``
    Adds deterministic ``ExperimentAsset`` files to the same local deployment,
    warms an isolated content-addressed cache, then lets ASV time fresh
    ``psynet export local --assets collected`` subprocesses. This compares the
    user-facing command without charging one commit for a shared cold cache.

Incremental remote asset transfer is intentionally not benchmarked here. That
path is important, but its warm-cache timings are dominated by filesystem noise
and should be covered by functional tests rather than the fast ASV gate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import inspect
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEMO_RELATIVE_PATH = Path("tests/experiments/static_big")

# The profiles below intentionally keep data shape separate from timing logic.
# If the demo changes in a way that alters row or asset counts, the validation
# helpers fail loudly and the corresponding ASV benchmark version should change.


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
    except ImportError:
        return False
    params = inspect.signature(export_assets).parameters
    return "collected_assets_only" in params


def _skip_unless_canonical_export_supported() -> None:
    """Skip this benchmark when the compared revision predates the API.

    ASV only treats ``NotImplementedError`` as a skip when it is raised from
    ``setup``, so each benchmark checks the installed revision before preparing
    its fixture.
    """
    if not _canonical_export_supported():
        raise NotImplementedError("Installed PsyNet predates the canonical export API.")


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


def _run_checked(command: list[str], *, cwd: Path, env: Optional[dict] = None) -> None:
    """Run a benchmark subprocess, raising if it fails."""

    subprocess.run(command, cwd=cwd, env=env or _benchmark_env(), check=True)


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


def _run_local_export(
    export_path: Path,
    *,
    assets: str = "none",
    env: Optional[dict] = None,
) -> None:
    """Run the canonical local export command."""

    _run_checked(
        [
            "psynet",
            "export",
            "local",
            "--assets",
            assets,
            "--path",
            str(export_path),
        ],
        cwd=_demo_dir(),
        env=env,
    )


def _fresh_export_path(export_root: Path) -> Path:
    """Return a new export path that does not yet exist."""

    return export_root / f"timed-{uuid.uuid4().hex}"


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


def _validate_export(
    export_path: Path,
    expected_table_rows: tuple[tuple[str, int], ...],
) -> None:
    """Validate that a canonical export has the expected table rows."""

    table_row_counts = _database_table_row_counts(export_path)
    expected = dict(expected_table_rows)
    actual = {table: table_row_counts.get(table, 0) for table in expected}
    if actual != expected:
        raise RuntimeError(
            "Export benchmark fixture shape changed. "
            f"Expected table rows {expected}, got {actual}. "
            "Update the fixture expectations and benchmark version if intentional."
        )


# ``LocalAssetExport`` setup and timing helpers.
#
# Depositing ``ExperimentAsset`` rows imports experiment-local SQLAlchemy models
# and mutates deployment state, so that setup happens in
# ``export_benchmark_worker.py``. The timed operation remains here and uses the
# public CLI so the benchmark follows the path experiment authors run.


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
    storage_root: Path,
) -> None:
    """Deposit benchmark assets in a fresh Python process."""

    _run_checked(
        [
            "python",
            str(Path(__file__).with_name("export_benchmark_worker.py")),
            str(manifest_path),
            str(storage_root),
        ],
        cwd=_demo_dir(),
    )


def _asset_export_env(cache_root: Path) -> dict[str, str]:
    """Return subprocess environment for an isolated asset cache."""
    env = _benchmark_env()
    env["PSYNET_ASSET_CACHE_ROOT"] = str(cache_root)
    return env


def _warm_asset_export_fixture(
    export_root: Path,
    cache_root: Path,
    manifest: list[dict[str, str | int]],
) -> None:
    """Warm the asset cache once and validate the exported files."""

    validation_path = export_root / "validation"
    try:
        _run_local_export(
            validation_path, assets="collected", env=_asset_export_env(cache_root)
        )
        _validate_asset_export(validation_path, manifest)
    finally:
        shutil.rmtree(validation_path, ignore_errors=True)


def _validate_asset_export(
    export_path: Path,
    manifest: list[dict[str, str | int]],
) -> None:
    """Validate exported benchmark assets against their input manifest."""

    assets_root = export_path / "assets"
    if not assets_root.is_dir():
        assets_root = export_path

    for item in manifest:
        path = assets_root / str(item["export_path"])
        if not path.is_file():
            raise RuntimeError(
                "Asset export benchmark fixture shape changed. "
                f"Missing exported file {path}."
            )
        payload = path.read_bytes()
        if len(payload) != item["size_bytes"]:
            raise RuntimeError(
                f"Unexpected size for {path}: "
                f"expected {item['size_bytes']}, got {len(payload)}."
            )
        if hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Unexpected SHA-256 digest for {path}.")


class LocalExport:
    """Benchmark the canonical local export after a reproducible population run."""

    params = list(_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 5

    def setup(self, profile):
        """Populate and validate one database-export profile."""

        _skip_unless_canonical_export_supported()
        self._tempdir = tempfile.TemporaryDirectory(
            prefix="psynet-export-benchmark-"
        )
        self._export_root = Path(self._tempdir.name)

        try:
            fixture = _EXPORT_PROFILES[profile]
            _populate_local_experiment(fixture.n_bots)
            validation_path = self._export_root / "validation"
            _run_local_export(validation_path)
            _validate_export(validation_path, fixture.expected_table_rows)
            shutil.rmtree(validation_path, ignore_errors=True)
        except Exception:
            self._tempdir.cleanup()
            raise

    def time_export(self, profile):
        """Run the local export command into a fresh destination."""

        _run_local_export(_fresh_export_path(self._export_root))

    def teardown(self, profile):
        """Remove this profile's temporary files."""

        self._tempdir.cleanup()


class LocalAssetExport:
    """Benchmark the local export CLI with deterministic ExperimentAsset files."""

    params = list(_ASSET_EXPORT_PROFILES)
    param_names = ["profile"]
    timeout = 300
    version = 5

    def setup(self, profile):
        """Deposit and validate one asset-export profile."""

        _skip_unless_canonical_export_supported()
        self._tempdir = tempfile.TemporaryDirectory(
            prefix="psynet-asset-export-benchmark-"
        )
        root = Path(self._tempdir.name)
        self._export_root = root / "exports"
        self._storage_root = root / "storage"
        self._cache_root = root / "cache"
        input_root = root / "inputs"
        input_root.mkdir()

        try:
            _populate_local_experiment()
            manifest = _write_asset_payloads(
                input_root, _ASSET_EXPORT_PROFILES[profile]
            )
            manifest_path = input_root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            _run_asset_worker(manifest_path, self._storage_root)
            _warm_asset_export_fixture(self._export_root, self._cache_root, manifest)
        except Exception:
            self._tempdir.cleanup()
            raise

    def time_asset_export(self, profile):
        """Run the cache-warmed local asset export command."""

        _run_local_export(
            _fresh_export_path(self._export_root),
            assets="collected",
            env=_asset_export_env(self._cache_root),
        )

    def teardown(self, profile):
        """Remove this profile's temporary files."""

        self._tempdir.cleanup()
