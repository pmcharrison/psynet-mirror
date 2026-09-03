from pathlib import Path

import pytest

from benchmarks.fast.debug_launch import (
    _LEGACY_LOCAL_RUN_SCAFFOLD_PATHS,
    StaticFilesDebugLaunch,
    _local_run_scaffold_paths,
    _prepare_benchmark_experiment,
    _prepared_benchmark_experiment,
    _temporary_static_payload,
)
from benchmarks.fast.export_benchmarks import (
    _ASSET_EXPORT_PROFILES,
    IncrementalAssetTransfer,
    LocalAssetExport,
    LocalExport,
    _AssetExportProfile,
    _count_csv_rows,
    _deterministic_bytes,
    _run_incremental_transfer_benchmark,
    _summarize_asset_export,
    _summarize_export,
    _time_warmed_local_asset_export,
    _write_asset_payloads,
    _write_incremental_export_manifest,
    _write_incremental_remote_store,
)
from psynet.experiment_scaffold import scaffold_paths_required_for_local_run
from psynet.export.asset_cache import default_cache_root


def test_temporary_static_payload_is_created_and_cleaned_up(tmp_path):
    with _temporary_static_payload(tmp_path, count=3, file_size=7) as payload_dir:
        files = list(payload_dir.iterdir())
        assert len(files) == 3
        assert {file.stat().st_size for file in files} == {7}

    assert not payload_dir.exists()
    assert not (tmp_path / "static").exists()


def test_temporary_static_payload_preserves_existing_static_files(tmp_path):
    sentinel = tmp_path / "static" / "asv-generated" / "sentinel.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("keep me")

    with _temporary_static_payload(tmp_path, count=1, file_size=1) as payload_dir:
        assert payload_dir != sentinel.parent
        assert sentinel.read_text() == "keep me"

    assert sentinel.read_text() == "keep me"


def test_temporary_static_payload_preserves_files_created_during_launch(tmp_path):
    with _temporary_static_payload(tmp_path, count=1, file_size=1):
        runtime_file = tmp_path / "static" / "assets" / "runtime.txt"
        runtime_file.parent.mkdir()
        runtime_file.write_text("keep me")

    assert runtime_file.read_text() == "keep me"


def test_local_run_scaffold_paths_match_scaffold_helper():
    """Benchmark prep must track the scaffold module's local-run path set."""
    assert _local_run_scaffold_paths() == scaffold_paths_required_for_local_run()
    assert _LEGACY_LOCAL_RUN_SCAFFOLD_PATHS == scaffold_paths_required_for_local_run()


def test_prepared_benchmark_experiment_restores_created_scaffold(tmp_path):
    repo_root = tmp_path / "repo"
    templates = repo_root / "psynet" / "resources" / "experiment_scripts"
    templates.mkdir(parents=True)
    (templates / "Dockerfile").write_text("FROM python:3.13\n")
    (templates / "config.txt").write_text("[Config]\n")
    (templates / "test.py").write_text("# test\n")
    (templates / ".gitignore").write_text("*.pyc\n")

    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    (demo_dir / "experiment.py").write_text("class Exp:\n    pass\n")

    with _prepared_benchmark_experiment(demo_dir, repo_root) as created:
        assert created
        assert (demo_dir / "Dockerfile").exists()
        assert (demo_dir / "constraints.txt").exists()
        assert not (demo_dir / "docker").exists()

    assert not (demo_dir / "Dockerfile").exists()
    assert not (demo_dir / "constraints.txt").exists()
    assert not (demo_dir / "docker").exists()
    assert (demo_dir / "experiment.py").exists()


def test_prepare_benchmark_experiment_follows_scaffold_path_helper(
    tmp_path, monkeypatch
):
    """New local-run paths from scaffold are copied without editing the benchmark."""
    repo_root = tmp_path / "repo"
    templates = repo_root / "psynet" / "resources" / "experiment_scripts"
    templates.mkdir(parents=True)
    (templates / "Dockerfile").write_text("FROM template\n")
    (templates / "extra-required.txt").write_text("new\n")

    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()

    monkeypatch.setattr(
        "benchmarks.fast.debug_launch._local_run_scaffold_paths",
        lambda: frozenset({"Dockerfile", "extra-required.txt"}),
    )

    created = _prepare_benchmark_experiment(demo_dir, repo_root)

    assert (demo_dir / "Dockerfile").read_text() == "FROM template\n"
    assert (demo_dir / "extra-required.txt").read_text() == "new\n"
    assert demo_dir / "Dockerfile" in created
    assert demo_dir / "extra-required.txt" in created


def test_prepare_benchmark_experiment_skips_existing_files(tmp_path):
    repo_root = tmp_path / "repo"
    templates = repo_root / "psynet" / "resources" / "experiment_scripts"
    templates.mkdir(parents=True)
    (templates / "Dockerfile").write_text("FROM template\n")

    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    (demo_dir / "Dockerfile").write_text("FROM existing\n")

    created = _prepare_benchmark_experiment(demo_dir, repo_root)

    assert (demo_dir / "Dockerfile").read_text() == "FROM existing\n"
    assert demo_dir / "Dockerfile" not in created


def test_static_files_debug_launch_tracks_each_profile():
    benchmark = StaticFilesDebugLaunch()
    results = {profile: index for index, profile in enumerate(benchmark.params)}

    for profile, expected in results.items():
        assert benchmark.track_launch_time_s(results, profile) == expected


def test_export_benchmark_counts_csv_data_rows(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,value\n1,a\n2,b\n")

    assert _count_csv_rows(csv_path) == 2


def test_export_benchmark_summarizes_the_canonical_export(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "participant.csv").write_text("id,worker_id\n1,w1\n")
    (database_dir / "trial.csv").write_text("id,participant_id\n1,1\n2,1\n")

    expected_table_rows = (("participant", 1), ("trial", 2))
    summary = _summarize_export(
        tmp_path,
        export_time_s=1.25,
        expected_table_rows=expected_table_rows,
    )

    database_size = sum(
        path.stat().st_size for path in database_dir.rglob("*") if path.is_file()
    )
    assert summary == {
        "export_time_s": 1.25,
        "data_csv_count": 2,
        "data_row_count": 3,
        "database_size_bytes": database_size,
    }


def test_export_benchmark_rejects_changed_fixture_shape(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "participant.csv").write_text("id\n1\n2\n")

    with pytest.raises(RuntimeError, match="fixture shape changed"):
        _summarize_export(
            tmp_path,
            export_time_s=1.25,
            expected_table_rows=(("participant", 1),),
        )


@pytest.mark.parametrize(
    "benchmark_cls",
    [LocalExport, IncrementalAssetTransfer, LocalAssetExport],
)
def test_export_benchmark_setup_accepts_asv_call_without_cached_results(
    benchmark_cls,
):
    """When setup_cache returns None, ASV calls setup(profile) with no cache dict."""
    benchmark_cls().setup(benchmark_cls.params[0])


def test_export_benchmark_setup_skips_when_the_installed_api_is_missing(monkeypatch):
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._canonical_export_supported",
        lambda: False,
    )
    with pytest.raises(NotImplementedError, match="predates"):
        LocalExport().setup("static_big_single_bot")


def test_local_export_tracks_metrics():
    benchmark = LocalExport()
    profile = benchmark.params[0]
    results = {
        profile: {
            "export_time_s": 2.5,
            "data_row_count": 42,
            "database_size_bytes": 1024,
        }
    }

    assert benchmark.track_export_time_s(results, profile) == 2.5
    assert benchmark.track_data_row_count(results, profile) == 42
    assert benchmark.track_database_size_bytes(results, profile) == 1024


def test_incremental_transfer_benchmark_measures_cold_and_warm_caches(monkeypatch):
    """The warm run must reuse the cache instead of transferring again."""
    import shutil
    import subprocess
    from pathlib import Path

    calls = []

    def copying_rsync(cmd, check=False, **kwargs):
        calls.append(cmd)
        files_from = Path(cmd[cmd.index("--files-from") + 1])
        source = Path(str(cmd[-2]).rstrip("/"))
        dest = Path(str(cmd[-1]).rstrip("/"))
        for relative in files_from.read_text().splitlines():
            if not relative:
                continue
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("psynet.export.ssh_rsync.subprocess.run", copying_rsync)

    metrics = _run_incremental_transfer_benchmark(_tiny_asset_profile())

    assert metrics["asset_file_count"] == 2
    assert metrics["cold_transfer_time_s"] >= 0
    assert metrics["warm_transfer_time_s"] >= 0
    # One discarded transfer warms rsync and the OS page cache, then the
    # timed cold transfer copies into an empty application cache. The warm
    # transfer must still reuse that cache (no third rsync).
    assert len(calls) == 2


def test_incremental_fixture_writes_remote_objects_once(tmp_path):
    """Export manifests must reuse the remote store instead of rewriting objects."""
    profile = _tiny_asset_profile()
    remote_root = tmp_path / "remote"
    entries = _write_incremental_remote_store(remote_root, profile)
    objects_dir = remote_root / "objects" / "sha256"
    object_paths = sorted(objects_dir.iterdir())
    assert len(object_paths) == profile.file_count
    fingerprints = {path.name: path.stat().st_mtime_ns for path in object_paths}

    _write_incremental_export_manifest(tmp_path / "discard", entries)
    _write_incremental_export_manifest(tmp_path / "cold", entries)
    _write_incremental_export_manifest(tmp_path / "warm", entries)

    assert fingerprints == {path.name: path.stat().st_mtime_ns for path in object_paths}
    for name in ("discard", "cold", "warm"):
        manifest = tmp_path / name / "assets" / "manifest.csv"
        assert manifest.is_file()
        text = manifest.read_text()
        assert all(digest in text for _, digest in entries)


def test_incremental_transfer_tracks_cold_cache_metric_only():
    benchmark = IncrementalAssetTransfer()
    profile = benchmark.params[0]
    results = {profile: {"cold_transfer_time_s": 3.0, "warm_transfer_time_s": 0.2}}

    assert benchmark.track_cold_transfer_time_s(results, profile) == 3.0
    assert not hasattr(benchmark, "track_warm_transfer_time_s")


def test_asset_benchmark_payloads_are_deterministic():
    assert _deterministic_bytes("asset", 16) == _deterministic_bytes("asset", 16)
    assert _deterministic_bytes("asset", 16) != _deterministic_bytes("other", 16)


def _tiny_asset_profile():
    return _AssetExportProfile(
        file_count=2,
        file_size_bytes=4,
        key_prefix="small",
    )


def test_asset_benchmark_profiles_have_expected_scale():
    many_small = _ASSET_EXPORT_PROFILES["many_small_files"]
    few_large = _ASSET_EXPORT_PROFILES["few_large_files"]

    assert many_small.file_count == 10_000
    assert many_small.file_count * many_small.file_size_bytes == 10_240_000
    assert few_large.file_count == 10
    assert few_large.file_count * few_large.file_size_bytes == 104_857_600


def test_asset_benchmark_writes_payload_manifest(tmp_path):
    profile = _tiny_asset_profile()
    manifest = _write_asset_payloads(tmp_path, profile)

    assert len(manifest) == profile.file_count
    assert sum(item["size_bytes"] for item in manifest) == 8
    for item in manifest:
        path = tmp_path / f"{item['key']}.bin"
        assert path.exists()
        assert path.stat().st_size == item["size_bytes"]


def test_asset_benchmark_summarizes_exported_files(tmp_path):
    profile = _tiny_asset_profile()
    input_dir = tmp_path / "input"
    export_dir = tmp_path / "export"
    input_dir.mkdir()
    export_dir.mkdir()
    manifest = _write_asset_payloads(input_dir, profile)

    for item in manifest:
        target = export_dir / item["export_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((input_dir / f"{item['key']}.bin").read_bytes())

    summary = _summarize_asset_export(
        export_dir,
        export_time_s=0.5,
        manifest=manifest,
    )

    assert summary == {
        "asset_export_time_s": 0.5,
        "asset_file_count": 2,
        "asset_total_bytes": 8,
    }


def test_asset_benchmark_rejects_changed_fixture_shape(tmp_path):
    profile = _tiny_asset_profile()
    input_dir = tmp_path / "input"
    export_dir = tmp_path / "export"
    input_dir.mkdir()
    export_dir.mkdir()
    manifest = _write_asset_payloads(input_dir, profile)

    first = manifest[0]
    target = export_dir / first["export_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes((input_dir / f"{first['key']}.bin").read_bytes())

    with pytest.raises(RuntimeError, match="fixture shape changed"):
        _summarize_asset_export(export_dir, export_time_s=0.5, manifest=manifest)


def test_local_asset_export_tracks_metrics():
    benchmark = LocalAssetExport()
    profile = benchmark.params[0]
    results = {
        profile: {
            "asset_export_time_s": 0.75,
            "asset_file_count": 10_000,
            "asset_total_bytes": 10_240_000,
        }
    }

    assert benchmark.track_asset_export_time_s(results, profile) == 0.75
    assert benchmark.track_asset_file_count(results, profile) == 10_000
    assert benchmark.track_asset_total_bytes(results, profile) == 10_240_000


def test_warmed_local_asset_export_records_the_second_cli_export(monkeypatch, tmp_path):
    """``track_*`` has no ASV warmup; the recorded sample must not be the cold run."""

    export_dirs = []
    elapsed_times = iter([10.0, 0.25])

    def fake_export(export_path, *, assets, env):
        assert assets == "collected"
        assert env["PSYNET_ASSET_CACHE_ROOT"] == str(tmp_path / "cache")
        path = Path(export_path)
        export_dirs.append(path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "marker").write_text("exported")
        return next(elapsed_times)

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._time_local_export", fake_export
    )

    export_path, elapsed = _time_warmed_local_asset_export(tmp_path, tmp_path / "cache")

    assert elapsed == pytest.approx(0.25)
    assert len(export_dirs) == 2
    assert export_dirs[0].name == "warmup"
    assert export_dirs[1].name == "timed"
    assert export_path == export_dirs[1]
    assert not export_dirs[0].exists()
    assert (export_path / "marker").read_text() == "exported"


def test_warmed_local_asset_export_does_not_mutate_parent_cache_env(
    monkeypatch, tmp_path
):
    """ASV commits must not share ``~/psynet-data/cache/assets`` hits."""

    parent_cache = tmp_path / "parent-cache"
    monkeypatch.setenv("PSYNET_ASSET_CACHE_ROOT", str(parent_cache))

    def fake_export(export_path, *, assets, env):
        assert env["PSYNET_ASSET_CACHE_ROOT"] == str(tmp_path / "isolated-cache")
        Path(export_path).mkdir(parents=True, exist_ok=True)
        return 0.1

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._time_local_export", fake_export
    )

    _time_warmed_local_asset_export(tmp_path / "exports", tmp_path / "isolated-cache")

    assert default_cache_root() == parent_cache
