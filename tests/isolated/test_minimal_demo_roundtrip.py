"""Validate scaffold prompts and round trips on representative demos."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from psynet.command_line import (
    EXPERIMENT_SCAFFOLD_GENERATED_FILES,
    EXPERIMENT_SCAFFOLD_OPTIONAL_TEMPLATE_FILES,
    EXPERIMENT_SCAFFOLD_TEMPLATE_DIRECTORIES,
    EXPERIMENT_SCAFFOLD_TEMPLATE_FILES,
    prune_experiment_scaffold,
    scaffold_experiment_directory,
)
from psynet.pytest_psynet import (
    local_only,
    path_to_demo_experiment,
    path_to_demo_feature,
)
from psynet.utils import working_directory

ROUNDTRIP_DEMOS = [
    ("experiments/hello_world", Path(path_to_demo_experiment("hello_world"))),
    ("features/api", Path(path_to_demo_feature("api"))),
    ("experiments/vocabulary_test", Path(path_to_demo_experiment("vocabulary_test"))),
]

RUNTIME_DEMOS = [
    ("experiments/hello_world", Path(path_to_demo_experiment("hello_world"))),
    ("features/api", Path(path_to_demo_feature("api"))),
]

SCAFFOLD_ROOT_DIRS = {
    Path(relative_path).parts[0]
    for relative_path in EXPERIMENT_SCAFFOLD_TEMPLATE_FILES
    if len(Path(relative_path).parts) > 1
}
SCAFFOLD_ROOT_DIRS.update(EXPERIMENT_SCAFFOLD_TEMPLATE_DIRECTORIES)

SCAFFOLD_REMOVABLE_ROOT_FILES = {
    Path(relative_path).name
    for relative_path in EXPERIMENT_SCAFFOLD_TEMPLATE_FILES
    if len(Path(relative_path).parts) == 1 and Path(relative_path).name != "README.md"
}
SCAFFOLD_REMOVABLE_ROOT_FILES.update(EXPERIMENT_SCAFFOLD_OPTIONAL_TEMPLATE_FILES)
SCAFFOLD_REMOVABLE_ROOT_FILES.update(EXPERIMENT_SCAFFOLD_GENERATED_FILES)


def _hash_file(path: Path) -> str:
    """Return a stable hash for one file in a temporary demo copy."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_demo_to_tmp(src: Path, tmp_path: Path, label: str) -> Path:
    """Copy a demo into a temporary git repository for round-trip checks."""
    target = tmp_path / label.replace("/", "__")
    shutil.copytree(src, target)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    return target


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
        if (
            len(relative_path.parts) == 1
            and relative_path.name in SCAFFOLD_REMOVABLE_ROOT_FILES
        ):
            continue
        if relative_path.parts[0] in SCAFFOLD_ROOT_DIRS:
            continue

        snapshot[relative_path.as_posix()] = _hash_file(file_path)
    return snapshot


def test_minimal_demo_prompts_for_scaffold_before_debug():
    demo_path = Path(path_to_demo_feature("api"))

    result = _run_command(
        ["psynet", "debug", "local", "--legacy", "--no-browsers"], demo_path
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "Run 'psynet scaffold'" in combined_output
    assert "required PsyNet boilerplate files" in combined_output


def test_relative_imports_work_in_minimal_demo_without_init_py():
    demo_path = Path(path_to_demo_feature("api"))
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
        prune_experiment_scaffold(preserve_files={"README.md"})

    assert _preserved_snapshot(temp_demo) == original_snapshot

    with working_directory(temp_demo):
        scaffold_experiment_directory(include_optional_files=True)

    assert _preserved_snapshot(temp_demo) == original_snapshot

    required_paths = [
        ".gitignore",
        "Dockerfile",
        "config.txt",
        "test.py",
        "AGENTS.md",
        ".python-version",
        ".github/workflows/test.yml",
        ".vscode/launch.json",
        "docker/psynet",
    ]
    for relative_path in required_paths:
        assert (temp_demo / relative_path).exists(), f"{label} missing {relative_path}"


@local_only
@pytest.mark.parametrize("label, demo_path", RUNTIME_DEMOS)
def test_demo_roundtrip_runs_local_test_command(label, demo_path, tmp_path):
    temp_demo = _copy_demo_to_tmp(demo_path, tmp_path, label)

    with working_directory(temp_demo):
        prune_experiment_scaffold(preserve_files={"README.md"})
        scaffold_experiment_directory(include_optional_files=True)

    result = _run_command(["psynet", "test", "local"], temp_demo)

    assert result.returncode == 0, (
        f"{label} failed after scaffold round-trip\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
