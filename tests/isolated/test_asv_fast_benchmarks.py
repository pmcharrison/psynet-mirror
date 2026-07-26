from benchmarks.fast.debug_launch import (
    StaticFilesDebugLaunch,
    _temporary_static_payload,
)
from benchmarks.fast.export_benchmarks import (
    LegacyLocalExport,
    _count_csv_rows,
    _summarize_export,
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
    data_dir = tmp_path / "regular" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "Participant.csv").write_text("id,worker_id\n1,w1\n")
    (data_dir / "Trial.csv").write_text("id,participant_id\n1,1\n2,1\n")
    (tmp_path / "regular" / "database.zip").write_bytes(b"snapshot")

    summary = _summarize_export(tmp_path, export_time_s=1.25)

    assert summary == {
        "export_time_s": 1.25,
        "data_csv_count": 2,
        "data_row_count": 3,
        "database_zip_size_bytes": 8,
    }


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
