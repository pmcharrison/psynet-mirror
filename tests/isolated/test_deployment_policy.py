import shutil
import subprocess
import tomllib
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dallinger.deployment_plan import build_deployment_plan, parse_deployment_policy
from dallinger.utils import ExperimentFileSource

from psynet.experiment import Experiment
from psynet.experiment_scaffold import (
    _GENERATED_DOCKERIGNORE_LINES,
    scaffold_experiment_directory,
)
from psynet.timeline import PreDeployRoutine
from psynet.utils import get_psynet_root, working_directory

EXPECTED_EXCLUDE_PATHS = (
    ".deploy",
    "data",
    "deploy",
    "deploy_logs",
    "develop",
    "local_only",
    "snapshots",
    "static/assets",
)

EXPECTED_EXCLUDE_NAMES = (
    ".env",
    ".pytest_cache",
    ".python-version",
    ".venv",
    "__pycache__",
    "logs.jsonl",
    "node_modules",
    "server.log",
    "source_code.zip",
)

EXPECTED_EXCLUDE_SUFFIXES = (
    ".db",
    ".dmg",
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
        assert "is not supported on Windows" in text
        assert "POSIX" in text


def _template_directory():
    return get_psynet_root() / "psynet" / "resources" / "experiment_scripts"


def test_generated_deployment_policy_is_valid_and_replaces_dockerignore():
    template_directory = _template_directory()
    policy = parse_deployment_policy(template_directory / "deploy.toml")

    assert policy.version == 1
    assert policy.exclude_paths == EXPECTED_EXCLUDE_PATHS
    assert policy.exclude_names == EXPECTED_EXCLUDE_NAMES
    assert policy.exclude_suffixes == EXPECTED_EXCLUDE_SUFFIXES
    assert not (template_directory / ".dockerignore").exists()


def test_stock_policy_covers_dallinger_starter_paths():
    """Fail when Dallinger adds a generic starter path that PsyNet omitted."""
    from dallinger.command_line.deployment_files import (
        _STARTER_EXCLUDE_NAMES,
        _STARTER_EXCLUDE_PATHS,
        _STARTER_EXCLUDE_SUFFIXES,
    )

    policy = parse_deployment_policy(_template_directory() / "deploy.toml")
    missing_paths = tuple(
        path for path in _STARTER_EXCLUDE_PATHS if path not in policy.exclude_paths
    )
    missing_names = tuple(
        name for name in _STARTER_EXCLUDE_NAMES if name not in policy.exclude_names
    )
    missing_suffixes = tuple(
        suffix
        for suffix in _STARTER_EXCLUDE_SUFFIXES
        if suffix not in policy.exclude_suffixes
    )
    assert missing_paths == (), (
        "PsyNet's stock deploy.toml is missing Dallinger starter exclude "
        "paths: " + ", ".join(missing_paths) + ". Review whether to add them to "
        "psynet/resources/experiment_scripts/deploy.toml."
    )
    assert missing_names == (), (
        "PsyNet's stock deploy.toml is missing Dallinger starter exclude "
        "names: " + ", ".join(missing_names) + ". Review whether to add them to "
        "psynet/resources/experiment_scripts/deploy.toml."
    )
    assert missing_suffixes == (), (
        "PsyNet's stock deploy.toml is missing Dallinger starter exclude "
        "suffixes: " + ", ".join(missing_suffixes) + ". Review whether to add them to "
        "psynet/resources/experiment_scripts/deploy.toml."
    )


def test_scaffold_creates_stock_deployment_policy(tmp_path):
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory()

    policy = parse_deployment_policy(tmp_path / "deploy.toml")
    assert policy.exclude_paths == EXPECTED_EXCLUDE_PATHS
    assert policy.exclude_names == EXPECTED_EXCLUDE_NAMES
    assert policy.exclude_suffixes == EXPECTED_EXCLUDE_SUFFIXES
    assert not (tmp_path / ".dockerignore").exists()


def test_scripts_update_replaces_generated_dockerignore(tmp_path):
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text("\n".join(_GENERATED_DOCKERIGNORE_LINES) + "\n")
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory(overwrite=True)

    assert (tmp_path / "deploy.toml").read_bytes() == (
        _template_directory() / "deploy.toml"
    ).read_bytes()
    assert not dockerignore.exists()


def test_scripts_update_preserves_existing_deployment_policy(tmp_path):
    contents = (
        '# Experiment-specific review\nversion = 1\n[exclude]\npaths = ["custom-local"]\n'
    ).encode()
    policy = tmp_path / "deploy.toml"
    policy.write_bytes(contents)
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory(overwrite=True)

    assert policy.read_bytes() == contents


def test_scripts_update_preserves_custom_dockerignore(tmp_path, capsys):
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text("custom-local-file\n")
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory(overwrite=True)

    assert dockerignore.read_text() == "custom-local-file\n"
    assert "must be moved to deploy.toml" in capsys.readouterr().err


def test_check_experiment_directory_creates_missing_deploy_toml(tmp_path, monkeypatch):
    from psynet.command_line import _check_experiment_directory

    monkeypatch.setattr("psynet.command_line.is_in_repo_experiment", lambda: False)
    monkeypatch.setattr("psynet.command_line.git_repository_available", lambda: True)
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory()
        Path("deploy.toml").unlink()
        _check_experiment_directory("debug")

    assert (tmp_path / "deploy.toml").read_bytes() == (
        _template_directory() / "deploy.toml"
    ).read_bytes()


def test_check_experiment_directory_preserves_existing_deploy_toml(
    tmp_path, monkeypatch
):
    from psynet.command_line import _check_experiment_directory

    monkeypatch.setattr("psynet.command_line.is_in_repo_experiment", lambda: False)
    monkeypatch.setattr("psynet.command_line.git_repository_available", lambda: True)
    contents = b'version = 1\n[exclude]\npaths = ["custom-local"]\n'
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    (tmp_path / "deploy.toml").write_bytes(contents)

    with working_directory(tmp_path):
        scaffold_experiment_directory()
        _check_experiment_directory("debug")

    assert (tmp_path / "deploy.toml").read_bytes() == contents


def test_check_experiment_directory_removes_generated_dockerignore(
    tmp_path, monkeypatch
):
    from psynet.command_line import _check_experiment_directory

    monkeypatch.setattr("psynet.command_line.is_in_repo_experiment", lambda: False)
    monkeypatch.setattr("psynet.command_line.git_repository_available", lambda: True)
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    dockerignore = tmp_path / ".dockerignore"

    with working_directory(tmp_path):
        scaffold_experiment_directory()
        dockerignore.write_text("\n".join(_GENERATED_DOCKERIGNORE_LINES) + "\n")
        _check_experiment_directory("debug")

    assert (tmp_path / "deploy.toml").exists()
    assert not dockerignore.exists()


def test_check_experiment_directory_warns_on_custom_dockerignore(
    tmp_path, monkeypatch, capsys
):
    from psynet.command_line import _check_experiment_directory

    monkeypatch.setattr("psynet.command_line.is_in_repo_experiment", lambda: False)
    monkeypatch.setattr("psynet.command_line.git_repository_available", lambda: True)
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    dockerignore = tmp_path / ".dockerignore"

    with working_directory(tmp_path):
        scaffold_experiment_directory()
        dockerignore.write_text("custom-local-file\n")
        capsys.readouterr()
        _check_experiment_directory("debug")

    assert dockerignore.read_text() == "custom-local-file\n"
    assert "must be moved to deploy.toml" in capsys.readouterr().err


def test_check_experiment_directory_removes_obsolete_docker_helpers(
    tmp_path, monkeypatch
):
    from psynet.command_line import _check_experiment_directory

    monkeypatch.setattr("psynet.command_line.is_in_repo_experiment", lambda: False)
    monkeypatch.setattr("psynet.command_line.git_repository_available", lambda: True)
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory()
        _write_obsolete_docker_helpers(tmp_path)
        _check_experiment_directory("debug")

    assert not (tmp_path / "docker").exists()


def _write_obsolete_docker_helpers(root):
    docker = root / "docker"
    docker.mkdir()
    (docker / "run").write_text("#!/bin/bash\n. docker/build\n")
    (docker / "psynet").write_text('#!/bin/bash\n./docker/run psynet "$@"\n')
    docs = docker / "docs"
    docs.mkdir()
    (docs / "RUN.md").write_text("# Running instructions\n")


def test_scaffold_does_not_create_docker_helpers(tmp_path):
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory()

    assert not (tmp_path / "docker").exists()
    assert (tmp_path / "Dockerfile").exists()
    assert not (_template_directory() / "docker").exists()


def test_scaffold_overwrite_removes_obsolete_docker_helpers(tmp_path):
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    _write_obsolete_docker_helpers(tmp_path)

    with working_directory(tmp_path):
        scaffold_experiment_directory(overwrite=True)

    assert not (tmp_path / "docker").exists()


def test_scripts_update_preserves_custom_docker_files(tmp_path, capsys):
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    _write_obsolete_docker_helpers(tmp_path)
    (tmp_path / "docker" / "custom").write_text("# keep me\n")

    with working_directory(tmp_path):
        scaffold_experiment_directory(overwrite=True)

    assert (tmp_path / "docker" / "custom").read_text() == "# keep me\n"
    assert not (tmp_path / "docker" / "run").exists()
    assert not (tmp_path / "docker" / "docs").exists()
    assert "Preserving custom files in docker/" in capsys.readouterr().err


def test_scaffold_preserves_symlinked_docker_docs_directory(tmp_path, capsys):
    (tmp_path / "experiment.py").write_text("class Exp:\n    pass\n")
    (tmp_path / "requirements.txt").write_text("psynet\n")
    docker = tmp_path / "docker"
    docker.mkdir()
    (docker / "run").write_text("#!/bin/bash\n")
    outside = tmp_path / "outside-docs"
    outside.mkdir()
    (outside / "INSTALL.md").write_text("# keep me\n")
    (docker / "docs").symlink_to(outside, target_is_directory=True)

    with working_directory(tmp_path):
        scaffold_experiment_directory()

    assert (outside / "INSTALL.md").read_text() == "# keep me\n"
    assert (docker / "docs").is_symlink()
    assert not (docker / "run").exists()
    captured = capsys.readouterr()
    assert (
        "Preserving docker/docs/ because it is a symlink" in captured.out + captured.err
    )


class _TranslationPreDeployExperiment(Experiment):
    """Run the real translation pre-deploy routine without database side effects."""

    def __init__(self, locales_dir, locales):
        self._test_supported_locales = ["en", *locales]
        self.assets = MagicMock()
        self.timeline = MagicMock()
        self.timeline.modules = {}
        self.pre_deploy_routines = [
            PreDeployRoutine(
                "compile_translations_if_necessary",
                self.compile_translations_if_necessary,
                {
                    "locales_dir": str(locales_dir),
                    "namespace": "experiment",
                },
            )
        ]

    @property
    def supported_locales(self):
        return self._test_supported_locales


@pytest.mark.parametrize(
    ("relative_directory", "locales"),
    [
        ("demos/experiments/translation", ["de", "nl"]),
        ("tests/experiments/translation", ["nl"]),
    ],
)
def test_translation_pre_deploy_outputs_remain_deployable(
    tmp_path, relative_directory, locales
):
    experiment_root = tmp_path / "experiment"
    staging_root = tmp_path / "staging"
    shutil.copytree(
        get_psynet_root() / relative_directory,
        experiment_root,
        symlinks=True,
    )
    for path in experiment_root.glob("locales/*/LC_MESSAGES/experiment.mo"):
        path.unlink()
    subprocess.run(["git", "init", "-q"], cwd=experiment_root, check=True)

    with working_directory(experiment_root):
        scaffold_experiment_directory()
    with (experiment_root / ".gitignore").open("a", encoding="utf-8") as file:
        file.write("\n.python-version\n*.mo\n")
    assert (experiment_root / ".python-version").is_file()

    experiment = _TranslationPreDeployExperiment(experiment_root / "locales", locales)
    with working_directory(experiment_root), ExitStack() as stack:
        for method in [
            "update_deployment_id",
            "setup_experiment_config",
            "setup_experiment_variables",
            "create_database_snapshot",
        ]:
            stack.enter_context(patch.object(experiment, method))
        stack.enter_context(
            patch("psynet.experiment._write_pre_deploy_constant_registry")
        )
        experiment.pre_deploy()

    generated_destinations = {
        f"locales/{locale}/LC_MESSAGES/experiment.mo" for locale in locales
    }
    plan = build_deployment_plan(experiment_root)
    assert generated_destinations <= plan.destinations

    source = ExperimentFileSource(experiment_root)
    assert generated_destinations <= source.deployment_plan.destinations
    source.apply_to(staging_root)
    assert all((staging_root / path).is_file() for path in generated_destinations)


def test_scaffolded_debug_source_prepares_from_policy(tmp_path):
    experiment_root = tmp_path / "hello_world"
    shutil.copytree(
        get_psynet_root() / "demos" / "experiments" / "hello_world",
        experiment_root,
        symlinks=True,
    )
    staging_root = tmp_path / "staging"

    with working_directory(experiment_root):
        scaffold_experiment_directory()

    source = ExperimentFileSource(experiment_root)
    assert source.deployment_plan is not None
    source.apply_development_to(staging_root)
    assert (staging_root / "experiment.py").is_file()
    assert (staging_root / "deploy.toml").is_file()
    assert "experiment.py" in source.deployment_plan.destinations
    assert "deploy.toml" in source.deployment_plan.destinations
