import re
import tomllib
from pathlib import Path

from psynet.dev import ci as ci_module

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
DALLINGER_CONSTRAINTS = ROOT / "ci" / "dallinger-dev-requirements.txt"


def test_vendored_dallinger_constraints_match_pyproject_dependency():
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dallinger_dependency = next(
        dependency
        for dependency in pyproject["project"]["dependencies"]
        if dependency.startswith("dallinger[")
    )
    dependency_version_match = re.search(r">=(\d+\.\d+\.\d+)", dallinger_dependency)
    if dependency_version_match is None:
        assert (
            dallinger_dependency == "dallinger[docker] @ "
            "git+https://github.com/pmcharrison/Dallinger.git"
            "@67964de9f8ce3a2aa416e827c77e90bd6235a2e6"
        )
        constraints = DALLINGER_CONSTRAINTS.read_text(encoding="utf-8")
        assert (
            re.search(r"^dallinger(?:\[.*\])?\s*[=@<]", constraints, re.MULTILINE)
            is None
        )
        return
    dependency_version = dependency_version_match.group(1)

    constraints = DALLINGER_CONSTRAINTS.read_text(encoding="utf-8")
    snapshot_version = re.search(
        r"^# PsyNet CI snapshot for Dallinger release: v(\d+\.\d+\.\d+)$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)
    source_version = re.search(
        r"^# Source: https://raw\.githubusercontent\.com/Dallinger/Dallinger/v(\d+\.\d+\.\d+)/dev-requirements\.txt$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)

    assert snapshot_version == dependency_version
    assert source_version == dependency_version


def test_update_dallinger_constraints_command_writes_header_and_validates(
    tmp_path, monkeypatch
):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
    "dallinger[docker]>=12.2.0,<13",
]
""",
        encoding="utf-8",
    )
    constraints = tmp_path / "ci" / "dallinger-dev-requirements.txt"
    constraints.parent.mkdir()
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("ARG PYTHON_VERSION=3.13\n", encoding="utf-8")
    compile_checks = []

    monkeypatch.setattr(ci_module, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(ci_module, "DOCKERFILE_PATH", dockerfile)
    monkeypatch.setattr(ci_module, "DALLINGER_CONSTRAINTS_PATH", constraints)
    monkeypatch.setattr(
        ci_module,
        "_download_text",
        lambda url: "# Dallinger generated header\nrequests==2.33.1\n",
    )
    monkeypatch.setattr(
        ci_module,
        "_check_docker_constraints_compile",
        lambda pyproject_path, constraints_path, dockerfile_path: compile_checks.append(
            (pyproject_path, constraints_path, dockerfile_path)
        ),
    )

    assert ci_module.update_dallinger_constraints_command() == 0

    text = constraints.read_text(encoding="utf-8")
    assert text.startswith(
        "# PsyNet CI snapshot for Dallinger release: v12.2.0\n"
        "# Source: https://raw.githubusercontent.com/Dallinger/Dallinger/v12.2.0/dev-requirements.txt\n"
    )
    assert text.endswith("# Dallinger generated header\nrequests==2.33.1\n")
    assert compile_checks == [(pyproject, constraints, dockerfile)]


def test_get_docker_python_version(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "ARG DOCKER_PLATFORM=linux/amd64\nARG PYTHON_VERSION=3.13\n",
        encoding="utf-8",
    )

    assert ci_module._get_docker_python_version(dockerfile) == "3.13"
