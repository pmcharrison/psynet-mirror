import subprocess
import tomllib
from pathlib import Path

import click
import pytest
from dallinger.deployment_plan import (
    build_deployment_plan,
    compare_legacy_deployment_selection,
    parse_deployment_policy,
)
from dallinger.utils import ExperimentFileSource

from psynet import command_line
from psynet.command_line import update_scripts_
from psynet.utils import get_psynet_root, list_experiment_dirs, working_directory

EXPECTED_EXCLUSIONS = (
    ".deploy",
    ".env",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "data",
    "deploy",
    "deploy_logs",
    "develop",
    "local_only",
    "logs.jsonl",
    "node_modules",
    "server.log",
    "snapshots",
    "source_code.zip",
    "static/assets",
)


def test_prototype_metadata_and_platform_warnings():
    root = get_psynet_root()
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    classifiers = project["classifiers"]

    assert project["requires-python"] == ">=3.11"
    assert "Programming Language :: Python :: 3.10" not in classifiers
    assert "Operating System :: POSIX" in classifiers
    assert "Operating System :: OS Independent" not in classifiers

    documentation = [
        root / "docs" / "deploy" / "index.rst",
        root / "docs" / "dependencies" / "docker.rst",
        root / "docs" / "experiment_development" / "experiment_directory.rst",
    ]
    for path in documentation:
        text = " ".join(path.read_text().split())
        assert ".. warning::" in text
        assert "POSIX descriptor-relative filesystem traversal" in text
        assert "is not supported on Windows" in text
        assert "carve-out is required before production rollout" in text
        assert "Policy-free experiments" in text
        assert "cross-platform" in text


def _template_directory():
    return get_psynet_root() / "psynet" / "resources" / "experiment_scripts"


def _managed_experiment_directories():
    root = get_psynet_root()
    return [Path(path) for path in list_experiment_dirs()] + [
        root / "tests" / "playwright" / "experiments" / "deferred_page_scripts"
    ]


def test_generated_deployment_policy_is_valid_and_replaces_dockerignore():
    template_directory = _template_directory()
    policy = parse_deployment_policy(template_directory / "deploy.toml")

    assert policy.version == 1
    assert policy.exclude == EXPECTED_EXCLUSIONS
    assert not (template_directory / ".dockerignore").exists()


def test_managed_experiments_have_synchronized_deployment_policy():
    template = (_template_directory() / "deploy.toml").read_bytes()
    directories = _managed_experiment_directories()

    assert len(directories) == 126
    assert all(
        (directory / "deploy.toml").read_bytes() == template
        for directory in directories
    )
    assert all(not (directory / ".dockerignore").exists() for directory in directories)


def test_all_managed_policies_match_legacy_membership():
    required = {
        "constraints.txt",
        "deploy.toml",
        "experiment.py",
        "requirements.txt",
    }

    for directory in _managed_experiment_directories():
        plan = build_deployment_plan(directory)
        comparison = compare_legacy_deployment_selection(plan)

        assert not comparison.unresolved_backend_ignore_controls, directory
        assert not comparison.newly_included, directory
        assert not comparison.newly_excluded, directory
        assert required <= plan.destinations, directory
        for optional in [".python-version", "Dockerfile"]:
            if (directory / optional).exists():
                assert optional in plan.destinations, directory


def test_update_scripts_replaces_generated_dockerignore(tmp_path):
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text(
        "\n".join(command_line._GENERATED_DOCKERIGNORE_LINES) + "\n",
        encoding="utf-8",
    )

    with working_directory(tmp_path):
        update_scripts_()

    assert (tmp_path / "deploy.toml").read_bytes() == (
        _template_directory() / "deploy.toml"
    ).read_bytes()
    assert not dockerignore.exists()


def test_update_scripts_preserves_existing_deployment_policy(tmp_path):
    contents = (
        "# Experiment-specific review\n"
        "version = 1\n"
        'legacy_diff_acknowledgement = "sha256:' + "0" * 64 + '"\n'
        'exclude = ["custom-local"]\n'
    ).encode()
    policy = tmp_path / "deploy.toml"
    policy.write_bytes(contents)

    with working_directory(tmp_path):
        update_scripts_()

    assert policy.read_bytes() == contents


def test_update_scripts_preserves_custom_dockerignore(tmp_path, capsys):
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text("custom-local-file\n", encoding="utf-8")

    with working_directory(tmp_path):
        update_scripts_()

    assert dockerignore.read_text(encoding="utf-8") == "custom-local-file\n"
    assert "must be moved to deploy.toml" in capsys.readouterr().err


class _PrecheckExperiment:
    def check_config(self):
        pass

    def check_consents(self):
        pass

    def check_python_dependencies(self):
        pass


def test_policy_experiment_prechecks_still_require_git(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "deploy.toml").write_text(
        "version = 1\nexclude = []\n", encoding="utf-8"
    )
    monkeypatch.setattr(command_line, "git_repository_available", lambda: False)
    monkeypatch.setattr(
        "psynet.experiment.get_experiment", lambda: _PrecheckExperiment()
    )

    with (
        working_directory(tmp_path),
        pytest.raises(click.ClickException, match="not a git repository"),
    ):
        command_line.run_pre_checks(mode="debug", local_=True)


def test_direct_docker_build_refuses_policy_experiment(tmp_path):
    (tmp_path / "deploy.toml").write_text(
        "version = 1\nexclude = []\n", encoding="utf-8"
    )
    script = _template_directory() / "docker" / "build"

    result = subprocess.run(
        ["bash", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "does not honor deploy.toml" in result.stderr
    assert "standard PsyNet/Dallinger commands" in result.stderr


def test_managed_direct_docker_build_scripts_match_template():
    template = (_template_directory() / "docker" / "build").read_bytes()
    directories = [
        directory
        for directory in _managed_experiment_directories()
        if (directory / "docker" / "build").is_file()
    ]

    assert len(directories) == 124
    assert all(
        (directory / "docker" / "build").read_bytes() == template
        for directory in directories
    )


def test_representative_debug_source_prepares_from_policy(tmp_path):
    root = get_psynet_root() / "demos" / "experiments" / "hello_world"
    source = ExperimentFileSource(root)

    assert source.deployment_plan is not None
    source.apply_development_to(tmp_path)
    assert (tmp_path / "deploy.toml").is_file()
    assert (tmp_path / "experiment.py").is_file()
