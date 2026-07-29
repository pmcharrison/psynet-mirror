from benchmarks.fast.debug_launch import (
    StaticFilesDebugLaunch,
    _prepare_benchmark_experiment,
    _prepared_benchmark_experiment,
    _temporary_static_payload,
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


def test_prepared_benchmark_experiment_restores_created_scaffold(tmp_path):
    repo_root = tmp_path / "repo"
    templates = repo_root / "psynet" / "resources" / "experiment_scripts"
    templates.mkdir(parents=True)
    (templates / "Dockerfile").write_text("FROM python:3.13\n")
    (templates / "config.txt").write_text("[Config]\n")
    (templates / "test.py").write_text("# test\n")
    (templates / ".gitignore").write_text("*.pyc\n")
    (templates / "__init__.py").write_text("")
    (templates / "pytest.ini").write_text("[pytest]\n")
    (templates / ".python-version").write_text("3.13\n")
    docker_templates = templates / "docker"
    docker_templates.mkdir()
    (docker_templates / "psynet").write_text("#!/bin/bash\n")

    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    (demo_dir / "experiment.py").write_text("class Exp:\n    pass\n")

    with _prepared_benchmark_experiment(demo_dir, repo_root) as created:
        assert created
        assert (demo_dir / "Dockerfile").exists()
        assert (demo_dir / "constraints.txt").exists()
        assert (demo_dir / "docker" / "psynet").exists()

    assert not (demo_dir / "Dockerfile").exists()
    assert not (demo_dir / "constraints.txt").exists()
    assert not (demo_dir / "docker").exists()
    assert (demo_dir / "experiment.py").exists()


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
