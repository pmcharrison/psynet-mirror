import pytest

from benchmarks.fast.debug_launch import (
    StaticFilesDebugLaunch,
    _temporary_static_payload,
)
from benchmarks.fast.export_benchmarks import (
    _ASSET_EXPORT_PROFILES,
    LegacyLocalExport,
    LocalAssetExport,
    _AssetExportProfile,
    _count_csv_rows,
    _deterministic_bytes,
    _summarize_asset_export,
    _summarize_export,
    _write_asset_payloads,
)


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


def test_static_files_debug_launch_tracks_each_profile():
    benchmark = StaticFilesDebugLaunch()
    results = {profile: index for index, profile in enumerate(benchmark.params)}

    for profile, expected in results.items():
        assert benchmark.track_launch_time_s(results, profile) == expected


def test_export_benchmark_counts_csv_data_rows(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,value\n1,a\n2,b\n")

    assert _count_csv_rows(csv_path) == 2


def test_export_benchmark_summarizes_legacy_export(tmp_path):
    import zipfile

    database_zip = tmp_path / "database.zip"
    with zipfile.ZipFile(database_zip, "w") as archive:
        archive.writestr("data/participant.csv", "id,worker_id\n1,w1\n")
        archive.writestr("data/trial.csv", "id,participant_id\n1,1\n2,1\n")

    expected_table_rows = (("participant", 1), ("trial", 2))
    summary = _summarize_export(
        tmp_path,
        export_time_s=1.25,
        expected_table_rows=expected_table_rows,
    )

    assert summary == {
        "export_time_s": 1.25,
        "data_csv_count": 2,
        "data_row_count": 3,
        "database_zip_size_bytes": database_zip.stat().st_size,
    }


def test_export_benchmark_rejects_changed_fixture_shape(tmp_path):
    import zipfile

    database_zip = tmp_path / "database.zip"
    with zipfile.ZipFile(database_zip, "w") as archive:
        archive.writestr("data/participant.csv", "id\n1\n2\n")

    with pytest.raises(RuntimeError, match="fixture shape changed"):
        _summarize_export(
            tmp_path,
            export_time_s=1.25,
            expected_table_rows=(("participant", 1),),
        )


def test_legacy_local_export_tracks_metrics():
    benchmark = LegacyLocalExport()
    profile = benchmark.params[0]
    results = {
        profile: {
            "export_time_s": 2.5,
            "data_row_count": 42,
            "database_zip_size_bytes": 1024,
        }
    }

    assert benchmark.track_export_time_s(results, profile) == 2.5
    assert benchmark.track_data_row_count(results, profile) == 42
    assert benchmark.track_database_zip_size_bytes(results, profile) == 1024


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
