import hashlib
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
    LocalAssetExport,
    LocalExport,
    _AssetExportProfile,
    _count_csv_rows,
    _deterministic_bytes,
    _validate_asset_export,
    _validate_export,
    _warm_asset_export_fixture,
    _write_asset_payloads,
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


def test_export_benchmark_validates_the_canonical_export(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "participant.csv").write_text("id,worker_id\n1,w1\n")
    (database_dir / "trial.csv").write_text("id,participant_id\n1,1\n2,1\n")

    _validate_export(tmp_path, (("participant", 1), ("trial", 2)))


def test_export_benchmark_rejects_changed_fixture_shape(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "participant.csv").write_text("id\n1\n2\n")

    with pytest.raises(RuntimeError, match="fixture shape changed"):
        _validate_export(tmp_path, (("participant", 1),))


def test_export_benchmark_setup_skips_when_the_installed_api_is_missing(monkeypatch):
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._canonical_export_supported",
        lambda: False,
    )
    with pytest.raises(NotImplementedError, match="predates"):
        LocalExport().setup("static_big_single_bot")


def test_local_export_uses_linear_asv_lifecycle(monkeypatch):
    benchmark = LocalExport()
    profile = benchmark.params[0]
    calls = []

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._populate_local_experiment",
        lambda n_bots: None,
    )
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._validate_export",
        lambda export_path, expected_table_rows: None,
    )

    def fake_export(export_path, *, assets="none", env=None):
        calls.append((Path(export_path), assets, env))

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._run_local_export", fake_export
    )

    benchmark.setup(profile)
    export_root = benchmark._export_root
    benchmark.time_export(profile)
    benchmark.teardown(profile)

    assert len(calls) == 2
    assert calls[0][0] == export_root / "validation"
    assert calls[1][0].parent == export_root
    assert calls[1][0].name.startswith("timed-")
    assert all(assets == "none" and env is None for _, assets, env in calls)
    assert not export_root.exists()


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


def test_asset_benchmark_validates_exported_files(tmp_path):
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

    _validate_asset_export(export_dir, manifest)


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
        _validate_asset_export(export_dir, manifest)


def test_local_asset_export_uses_linear_asv_lifecycle(monkeypatch):
    benchmark = LocalAssetExport()
    profile = benchmark.params[0]
    calls = []
    manifest = [{"export_path": "asset.bin", "size_bytes": 1, "sha256": "digest"}]

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._populate_local_experiment",
        lambda: None,
    )
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._write_asset_payloads",
        lambda input_root, selected_profile: manifest,
    )
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._run_asset_worker",
        lambda manifest_path, storage_root: None,
    )
    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._warm_asset_export_fixture",
        lambda export_root, cache_root, actual_manifest: calls.append(
            ("warm", export_root, cache_root, actual_manifest)
        ),
    )

    def fake_export(export_path, *, assets="none", env=None):
        calls.append(("time", Path(export_path), assets, env))

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._run_local_export", fake_export
    )

    benchmark.setup(profile)
    root = Path(benchmark._tempdir.name)
    benchmark.time_asset_export(profile)
    benchmark.teardown(profile)

    assert calls[0] == (
        "warm",
        root / "exports",
        root / "cache",
        manifest,
    )
    assert calls[1][0] == "time"
    assert calls[1][1].parent == root / "exports"
    assert calls[1][1].name.startswith("timed-")
    assert calls[1][2] == "collected"
    assert calls[1][3]["PSYNET_ASSET_CACHE_ROOT"] == str(root / "cache")
    assert not root.exists()


def test_warm_asset_export_fixture_validates_and_cleans_up(monkeypatch, tmp_path):
    """The setup export warms the cache and validates the fixture shape."""

    payload = _deterministic_bytes("asset", 4)
    manifest = [
        {
            "export_path": "asset_benchmark/asset.bin",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]

    def fake_export(export_path, *, assets="none", env=None):
        assert assets == "collected"
        assert env["PSYNET_ASSET_CACHE_ROOT"] == str(tmp_path / "cache")
        path = Path(export_path)
        target = path / "assets" / "asset_benchmark" / "asset.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    monkeypatch.setattr(
        "benchmarks.fast.export_benchmarks._run_local_export", fake_export
    )

    _warm_asset_export_fixture(tmp_path, tmp_path / "cache", manifest)

    assert not (tmp_path / "validation").exists()


def test_asset_export_env_does_not_mutate_parent_cache_env(monkeypatch, tmp_path):
    """ASV commits must not share ``~/psynet-data/cache/assets`` hits."""

    parent_cache = tmp_path / "parent-cache"
    monkeypatch.setenv("PSYNET_ASSET_CACHE_ROOT", str(parent_cache))

    from benchmarks.fast.export_benchmarks import _asset_export_env

    env = _asset_export_env(tmp_path / "isolated-cache")

    assert env["PSYNET_ASSET_CACHE_ROOT"] == str(tmp_path / "isolated-cache")
    assert default_cache_root() == parent_cache
