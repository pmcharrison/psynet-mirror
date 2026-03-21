import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from demos.audit_minimal_demos import audit_demo_directory
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_demo_to_tmp(src: Path, tmp_path: Path, label: str) -> Path:
    target = tmp_path / label.replace("/", "__")
    shutil.copytree(src, target)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    return target


def _preserved_snapshot(root: Path) -> dict[str, str]:
    snapshot = {}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(root)
        if relative_path.parts[0] == ".git":
            continue
        if len(relative_path.parts) == 1 and relative_path.name in SCAFFOLD_REMOVABLE_ROOT_FILES:
            continue
        if relative_path.parts[0] in SCAFFOLD_ROOT_DIRS:
            continue

        snapshot[relative_path.as_posix()] = _hash_file(file_path)
    return snapshot


def test_audit_identifies_full_demo():
    record = audit_demo_directory(path_to_demo_experiment("hello_world"))

    assert record.already_minimal is False
    assert record.generic_readme is True
    assert "Dockerfile" in record.removable_root_files
    assert "docker" in record.removable_root_dirs
    assert "experiment.py" in record.preserved_root_files


def test_audit_identifies_pilot_minimal_demo():
    record = audit_demo_directory(path_to_demo_feature("api"))

    assert record.already_minimal is True
    assert record.generic_readme is False
    assert record.uses_relative_imports is True
    assert not record.removable_root_files
    assert not record.removable_root_dirs
    assert "custom_pages.py" in record.preserved_root_files
    assert "templates" in record.preserved_root_dirs


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

    result = subprocess.run(
        ["psynet", "test", "local"],
        cwd=temp_demo,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=240,
    )

    assert result.returncode == 0, (
        f"{label} failed after scaffold round-trip\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
