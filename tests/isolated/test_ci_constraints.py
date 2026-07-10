import re
from pathlib import Path

from psynet.dev import ci as ci_module

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
DALLINGER_CONSTRAINTS = ROOT / "ci" / "dallinger-dev-requirements.txt"


def test_vendored_dallinger_constraints_match_pyproject_dependency():
    dependency_reference = ci_module._get_dallinger_dependency_reference(PYPROJECT)

    constraints = DALLINGER_CONSTRAINTS.read_text(encoding="utf-8")
    snapshot_reference = re.search(
        r"^# PsyNet CI snapshot for Dallinger reference: ([^\s]+)$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)
    source_reference = re.search(
        r"^# Source: https://raw\.githubusercontent\.com/Dallinger/Dallinger/([^\s]+)/dev-requirements\.txt$",
        constraints,
        flags=re.MULTILINE,
    ).group(1)

    assert snapshot_reference == dependency_reference
    assert source_reference == dependency_reference


def test_update_dallinger_constraints_command_writes_header_and_validates(
    tmp_path, monkeypatch
):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
    "dallinger[docker] @ git+https://github.com/Dallinger/Dallinger.git@support-python3.11-to-3.14",
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
        "# PsyNet CI snapshot for Dallinger reference: support-python3.11-to-3.14\n"
        "# Source: https://raw.githubusercontent.com/Dallinger/Dallinger/support-python3.11-to-3.14/dev-requirements.txt\n"
    )
    assert text.endswith("# Dallinger generated header\nrequests==2.33.1\n")
    assert compile_checks == [(pyproject, constraints, dockerfile)]


def test_get_dallinger_dependency_reference_from_release(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["dallinger[docker]>=12.3.0,<13"]
""",
        encoding="utf-8",
    )

    assert ci_module._get_dallinger_dependency_reference(pyproject) == "v12.3.0"


def test_get_docker_python_version(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "ARG DOCKER_PLATFORM=linux/amd64\nARG PYTHON_VERSION=3.13\n",
        encoding="utf-8",
    )

    assert ci_module._get_docker_python_version(dockerfile) == "3.13"


def test_docker_constraints_compile_checks_all_supported_versions(
    tmp_path, monkeypatch
):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n", encoding="utf-8")
    constraints = tmp_path / "dallinger-dev-requirements.txt"
    constraints.write_text("", encoding="utf-8")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("ARG PYTHON_VERSION=3.13\n", encoding="utf-8")
    commands = []

    monkeypatch.setattr(
        ci_module.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command),
    )

    ci_module._check_docker_constraints_compile(
        pyproject,
        constraints,
        dockerfile,
    )

    assert [command[command.index("--python-version") + 1] for command in commands] == [
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    ]
