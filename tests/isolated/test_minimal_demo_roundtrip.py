"""Validate scaffold prompts and round trips on representative demos."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from psynet.experiment_scaffold import (
    prune_experiment_scaffold,
    scaffold_experiment_directory,
    scaffold_managed_paths,
)
from psynet.pytest_psynet import (
    local_only,
    path_to_demo_experiment,
    path_to_demo_feature,
)
from psynet.utils import get_psynet_root, working_directory

ROUNDTRIP_DEMOS = [
    ("experiments/hello_world", Path(path_to_demo_experiment("hello_world"))),
    ("features/api", Path(path_to_demo_feature("api"))),
    ("experiments/vocabulary_test", Path(path_to_demo_experiment("vocabulary_test"))),
]

RUNTIME_DEMOS = [
    ("experiments/hello_world", Path(path_to_demo_experiment("hello_world"))),
    ("features/api", Path(path_to_demo_feature("api"))),
]

SCAFFOLD_MANAGED_PATHS = {
    Path(relative_path)
    for relative_path in scaffold_managed_paths()
    if relative_path != "README.md"
}
PRUNABLE_RESOURCE_PATHS = {Path("templates/.keep")}


def test_demo_sources_contain_only_authored_experiment_files():
    psynet_root = get_psynet_root()
    demos_root = psynet_root / "demos"
    managed_paths = scaffold_managed_paths() - {"README.md"}
    tracked_paths = set(
        subprocess.check_output(
            ["git", "ls-files", "demos"],
            cwd=psynet_root,
            text=True,
        ).splitlines()
    )

    for experiment_file in demos_root.rglob("experiment.py"):
        demo = experiment_file.parent
        relative_demo = demo.relative_to(psynet_root)
        assert (relative_demo / "constraints.txt").as_posix() not in tracked_paths
        assert (demo / "requirements.txt").read_text().splitlines()[0] == "psynet"
        for relative_path in managed_paths:
            tracked_path = (relative_demo / relative_path).as_posix()
            assert tracked_path not in tracked_paths, (
                f"{demo} tracks scaffold-managed path {relative_path}"
            )


def test_skipped_dependency_check_does_not_require_constraints(monkeypatch):
    from psynet.experiment import Experiment

    monkeypatch.setenv("SKIP_DEPENDENCY_CHECK", "1")
    Experiment.check_python_dependencies(object())


def test_bundled_demo_dependency_check_does_not_require_constraints(monkeypatch):
    from psynet.experiment import Experiment

    monkeypatch.delenv("SKIP_DEPENDENCY_CHECK", raising=False)
    monkeypatch.setattr("psynet.experiment.is_bundled_demo", lambda: True)
    Experiment.check_python_dependencies(object())


def test_bundled_demo_dependency_check_ignores_leftover_constraints(
    tmp_path, monkeypatch
):
    from psynet.experiment import Experiment

    monkeypatch.delenv("SKIP_DEPENDENCY_CHECK", raising=False)
    monkeypatch.setattr("psynet.experiment.is_bundled_demo", lambda: True)
    (tmp_path / "constraints.txt").write_text("some-package==1.0.0\n")
    with working_directory(tmp_path):
        Experiment.check_python_dependencies(object())


def _hash_file(path: Path) -> str:
    """Return a stable hash for one file in a temporary demo copy."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_demo_to_tmp(src: Path, tmp_path: Path, label: str) -> Path:
    """Copy a demo into a temporary git repository for round-trip checks."""
    static_directory = (src / "static").resolve()

    def ignore_generated_paths(directory, names):
        if Path(directory).resolve() == static_directory and "assets" in names:
            return {"assets"}
        return set()

    target = tmp_path / label.replace("/", "__")
    shutil.copytree(src, target, ignore=ignore_generated_paths)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    return target


def test_copy_demo_to_tmp_ignores_generated_static_assets(tmp_path):
    source = tmp_path / "source"
    static = source / "static"
    static.mkdir(parents=True)
    (source / "experiment.py").write_text("class Exp:\n    pass\n")
    (static / "assets").symlink_to(tmp_path / "missing-assets")
    copies = tmp_path / "copies"
    copies.mkdir()

    copied = _copy_demo_to_tmp(source, copies, "demo")

    assert (copied / "experiment.py").exists()
    assert not (copied / "static/assets").exists()
    assert not (copied / "static/assets").is_symlink()


def _run_command(args, cwd: Path):
    """Run a subprocess in a demo directory and capture its output."""
    return subprocess.run(
        args,
        cwd=cwd,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=240,
    )


def _preserved_snapshot(root: Path) -> dict[str, str]:
    """Capture hashes for files that should survive scaffold pruning unchanged."""
    snapshot = {}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(root)
        if relative_path.parts[0] == ".git":
            continue
        if relative_path in PRUNABLE_RESOURCE_PATHS:
            continue
        if any(
            relative_path == managed_path or managed_path in relative_path.parents
            for managed_path in SCAFFOLD_MANAGED_PATHS
        ):
            continue

        snapshot[relative_path.as_posix()] = _hash_file(file_path)
    return snapshot


def test_minimal_demo_prompts_for_scaffold_before_debug(tmp_path):
    demo_path = _copy_demo_to_tmp(
        Path(path_to_demo_feature("api")), tmp_path, "features/api"
    )
    with working_directory(demo_path):
        prune_experiment_scaffold(preserve_files={"README.md"}, force=True)

    result = _run_command(
        ["psynet", "debug", "local", "--legacy", "--no-browsers"], demo_path
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "Run 'psynet scripts scaffold'" in combined_output
    assert "required PsyNet boilerplate files" in combined_output
    for required_path in (
        ".gitignore",
        "config.txt",
        "Dockerfile",
        "test.py",
        "docker",
    ):
        assert required_path in combined_output


def test_relative_imports_work_in_minimal_demo_without_init_py(tmp_path):
    demo_path = _copy_demo_to_tmp(
        Path(path_to_demo_feature("api")), tmp_path, "features/api"
    )
    with working_directory(demo_path):
        prune_experiment_scaffold(preserve_files={"README.md"}, force=True)

    assert not (demo_path / "__init__.py").exists()

    result = _run_command(
        [
            "python",
            "-c",
            (
                "from psynet.experiment import import_local_experiment; "
                "exp = import_local_experiment()['class'](); "
                "print(exp.__class__.__name__)"
            ),
        ],
        demo_path,
    )

    assert result.returncode == 0, result.stderr
    assert "Exp" in result.stdout


def test_scaffolded_copy_without_git_repo_prompts_for_git_init(tmp_path):
    source = Path(path_to_demo_feature("api"))
    temp_demo = tmp_path / "api_copy"
    shutil.copytree(source, temp_demo)

    with working_directory(temp_demo):
        scaffold_experiment_directory(include_optional_files=True)
        Path("constraints.txt").write_text("# Test-only dependency metadata\n")

    result = _run_command(
        ["psynet", "debug", "local", "--legacy", "--no-browsers"], temp_demo
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "git init" in combined_output
    assert "not a git repository" in combined_output


@pytest.mark.parametrize("label, demo_path", ROUNDTRIP_DEMOS)
def test_demo_roundtrip_preserves_authored_files(label, demo_path, tmp_path):
    temp_demo = _copy_demo_to_tmp(demo_path, tmp_path, label)
    original_snapshot = _preserved_snapshot(temp_demo)

    with working_directory(temp_demo):
        prune_experiment_scaffold(preserve_files={"README.md"}, force=True)

    assert _preserved_snapshot(temp_demo) == original_snapshot

    with working_directory(temp_demo):
        scaffold_experiment_directory(include_optional_files=True)

    assert _preserved_snapshot(temp_demo) == original_snapshot

    for relative_path in scaffold_managed_paths():
        assert (temp_demo / relative_path).exists(), f"{label} missing {relative_path}"


@local_only
@pytest.mark.parametrize("label, demo_path", RUNTIME_DEMOS)
def test_demo_roundtrip_runs_local_test_command(label, demo_path, tmp_path):
    temp_demo = _copy_demo_to_tmp(demo_path, tmp_path, label)

    with working_directory(temp_demo):
        prune_experiment_scaffold(preserve_files={"README.md"}, force=True)

    scaffold_result = _run_command(["psynet", "scripts", "scaffold"], temp_demo)
    assert scaffold_result.returncode == 0, scaffold_result.stderr

    result = _run_command(["psynet", "test", "local"], temp_demo)

    assert result.returncode == 0, (
        f"{label} failed after scaffold round-trip\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
