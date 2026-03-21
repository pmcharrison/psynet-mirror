import sys
from pathlib import Path

import pytest

CI_DIR = Path(__file__).resolve().parents[2] / "ci"
if str(CI_DIR) not in sys.path:
    sys.path.insert(0, str(CI_DIR))

import pytest_common  # noqa: E402
import run_ci_docker_command  # noqa: E402
import run_ci_tests  # noqa: E402
import run_docker_experiment_tests  # noqa: E402


def test_build_pytest_common_args_defaults():
    args = pytest_common.build_pytest_common_args(timeout_seconds=123)
    assert args == [
        "-Werror",
        "-W",
        pytest_common.WARNING_FILTER,
        "-o",
        "log_cli=False",
        "--chrome",
        "--timeout=123",
        "-q",
    ]


def test_build_pytest_common_args_diagnostic_mode():
    args = pytest_common.build_pytest_common_args(
        timeout_seconds=30, log_cli=True, quiet=False
    )
    assert "log_cli=True" in args
    assert "-q" not in args


def test_build_docker_run_command(monkeypatch):
    monkeypatch.setenv("POSTGRES_IP", "10.0.0.1")
    monkeypatch.setenv("REDIS_IP", "10.0.0.2")

    command = run_ci_docker_command.build_docker_run_command(
        image_tag="my-image",
        workspace_path="/workspace",
        workdir="/workspace",
        command=["python3", "ci/run_ci_tests.py"],
    )

    assert command[0:2] == ["docker", "run"]
    assert "--add-host=postgres:10.0.0.1" in command
    assert "--add-host=redis:10.0.0.2" in command
    assert command[-3:] == ["my-image", "python3", "ci/run_ci_tests.py"]


def test_build_docker_run_command_requires_service_ips(monkeypatch):
    monkeypatch.delenv("POSTGRES_IP", raising=False)
    monkeypatch.delenv("REDIS_IP", raising=False)

    with pytest.raises(RuntimeError, match="POSTGRES_IP and REDIS_IP must be set"):
        run_ci_docker_command.build_docker_run_command(
            image_tag="my-image",
            workspace_path="/workspace",
            workdir="/workspace",
            command=["python3"],
        )


def test_list_lines_strips_blanks(monkeypatch):
    monkeypatch.setattr(
        run_ci_tests.subprocess,
        "check_output",
        lambda command, text: "a\n\n  b  \n",
    )
    assert run_ci_tests.list_lines(["ignored"]) == ["a", "b"]


def test_install_ci_dependencies_calls_uv(monkeypatch):
    observed = {}

    def fake_run(command, check):
        observed["command"] = command
        observed["check"] = check
        return 0

    monkeypatch.setattr(run_ci_tests.subprocess, "run", fake_run)
    run_ci_tests.install_ci_dependencies("/tmp/workspace")
    assert observed["command"] == [
        "uv",
        "pip",
        "install",
        "--no-cache",
        "--system",
        "--no-deps",
        "-e",
        "/tmp/workspace",
    ]
    assert observed["check"] is True


def test_dependency_line_parsing_helpers():
    line = "  psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet\n"
    normalized = run_docker_experiment_tests.normalize_dependency_line(line)
    assert (
        normalized == "psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet"
    )
    assert run_docker_experiment_tests.extract_psynet_ref(normalized) == "master"


def test_rewrite_psynet_dependency_file_rewrites_master_pin(tmp_path):
    dependency_file = tmp_path / "requirements.txt"
    dependency_file.write_text(
        "psynet @ git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet\n"
    )

    found = run_docker_experiment_tests.rewrite_psynet_dependency_file(
        dependency_file, ci_commit_sha="abc123"
    )
    assert found is True
    assert "@abc123" in dependency_file.read_text()


def test_resolve_psynet_ref_prefers_mr_source_sha(monkeypatch):
    monkeypatch.setenv("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA", "source-sha")
    monkeypatch.setenv("CI_COMMIT_SHA", "merge-sha")

    assert run_docker_experiment_tests.resolve_psynet_ref_from_env() == "source-sha"


def test_resolve_psynet_ref_falls_back_to_ci_commit_sha(monkeypatch):
    monkeypatch.delenv("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA", raising=False)
    monkeypatch.setenv("CI_COMMIT_SHA", "commit-sha")

    assert run_docker_experiment_tests.resolve_psynet_ref_from_env() == "commit-sha"


def test_resolve_psynet_ref_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA", raising=False)
    monkeypatch.delenv("CI_COMMIT_SHA", raising=False)

    assert run_docker_experiment_tests.resolve_psynet_ref_from_env() is None


def test_regenerate_constraints_invokes_docker_when_requirements_present(
    monkeypatch, tmp_path
):
    (tmp_path / "requirements.txt").write_text("psynet\n")
    observed = {}

    def fake_run(command, check):
        observed["command"] = command
        observed["check"] = check
        return 0

    monkeypatch.setattr(run_docker_experiment_tests.subprocess, "run", fake_run)
    run_docker_experiment_tests.regenerate_constraints("base-image", tmp_path)
    assert observed["command"][0:3] == ["docker", "run", "--rm"]
    assert observed["command"][-3] == "sh"
    assert observed["command"][-2] == "-lc"
    assert (
        run_docker_experiment_tests.DALLINGER_CONSTRAINTS_GENERATOR_URL
        in observed["command"][-1]
    )
    assert "uv run - generate" in observed["command"][-1]
    assert observed["check"] is True


def test_regenerate_constraints_skips_when_requirements_missing(monkeypatch, tmp_path):
    called = {"value": False}

    def fake_run(command, check):
        called["value"] = True
        return 0

    monkeypatch.setattr(run_docker_experiment_tests.subprocess, "run", fake_run)
    run_docker_experiment_tests.regenerate_constraints("base-image", tmp_path)
    assert called["value"] is False
