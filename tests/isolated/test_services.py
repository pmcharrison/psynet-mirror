"""Tests for local PostgreSQL/Redis service checks and ensure helpers."""

from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from psynet.command_line import psynet
from psynet.services import (
    ServiceCheck,
    ensure_local_services,
    start_local_services_via_docker,
    verify_local_services,
)


def _ok_checks():
    return [
        ServiceCheck("PostgreSQL", True, "reachable"),
        ServiceCheck("Redis", True, "responded to PING"),
    ]


def _down_checks():
    return [
        ServiceCheck("PostgreSQL", False, "connection refused"),
        ServiceCheck("Redis", False, "connection refused"),
    ]


def test_services_check_succeeds_when_healthy(monkeypatch):
    monkeypatch.setattr(
        "psynet.services.check_local_services",
        _ok_checks,
    )
    result = CliRunner().invoke(psynet, ["services", "check"])
    assert result.exit_code == 0, result.output
    assert "PostgreSQL: OK" in result.output
    assert "Redis: OK" in result.output


def test_services_check_fails_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "psynet.services.check_local_services",
        _down_checks,
    )
    result = CliRunner().invoke(psynet, ["services", "check"])
    assert result.exit_code != 0
    assert "psynet services ensure" in result.output


def test_services_ensure_starts_when_needed(monkeypatch):
    calls = {"checks": 0, "started": False}

    def fake_checks():
        calls["checks"] += 1
        if calls["started"]:
            return _ok_checks()
        return _down_checks()

    monkeypatch.setattr("psynet.services.check_local_services", fake_checks)
    monkeypatch.setattr("psynet.services._is_interactive", lambda: False)

    def fake_start():
        calls["started"] = True

    monkeypatch.setattr("psynet.services.start_local_services_via_docker", fake_start)
    monkeypatch.setattr(
        "psynet.services._wait_until_services_ready",
        lambda timeout_seconds=30: _ok_checks(),
    )

    result = CliRunner().invoke(psynet, ["services", "ensure", "--yes"])
    assert result.exit_code == 0, result.output
    assert calls["started"] is True
    assert "Local services are ready." in result.output


def test_services_ensure_noninteractive_requires_yes(monkeypatch):
    monkeypatch.setattr("psynet.services.check_local_services", _down_checks)
    monkeypatch.setattr("psynet.services._is_interactive", lambda: False)
    monkeypatch.setattr(
        "psynet.services.start_local_services_via_docker",
        lambda: pytest.fail("must not start without --yes"),
    )

    result = CliRunner().invoke(psynet, ["services", "ensure"])
    assert result.exit_code != 0
    assert "--yes" in result.output


def test_verify_local_services_soft_warns(monkeypatch):
    monkeypatch.setattr("psynet.services.check_local_services", _down_checks)
    assert verify_local_services(strict=False) is False


def test_verify_local_services_strict_raises(monkeypatch):
    monkeypatch.setattr("psynet.services.check_local_services", _down_checks)
    with pytest.raises(click.ClickException, match="psynet services ensure"):
        verify_local_services(strict=True)


def test_ensure_local_services_soft_does_not_raise(monkeypatch):
    monkeypatch.setattr("psynet.services.check_local_services", _down_checks)
    monkeypatch.setattr("psynet.services._is_interactive", lambda: False)
    assert ensure_local_services(assume_yes=False, strict=False) is False


def test_start_local_services_requires_docker(monkeypatch):
    monkeypatch.setattr("psynet.services.docker_available", lambda: False)
    with pytest.raises(click.ClickException, match="Docker is not available"):
        start_local_services_via_docker()


def test_leftover_volume_does_not_look_like_a_container(monkeypatch):
    """A volume sharing the container name must not trigger 'docker start'."""
    from psynet.services import _ensure_docker_container

    commands = []

    def fake_run(args, **kwargs):
        commands.append(args)
        result = Mock()
        # Only volumes remain, so container-scoped inspects fail.
        result.returncode = 1 if "inspect" in args else 0
        result.stdout = ""
        result.stderr = ""
        return result

    monkeypatch.setattr("psynet.services.subprocess.run", fake_run)

    _ensure_docker_container("dallinger_redis", ["run", "-d", "redis"])

    inspect_commands = [args for args in commands if "inspect" in args]
    assert inspect_commands
    for args in inspect_commands:
        assert args[:3] == ["docker", "container", "inspect"]
    assert ["docker", "start", "dallinger_redis"] not in commands
    assert ["docker", "run", "-d", "redis"] in commands


def test_pre_launch_skips_service_ensure_for_docker_mode(monkeypatch):
    from psynet.command_line import _pre_launch

    ensure = Mock()
    monkeypatch.setattr("psynet.services.ensure_local_services", ensure)
    monkeypatch.setattr(
        "psynet.command_line._check_experiment_directory", lambda mode: None
    )
    monkeypatch.setattr(
        "psynet.command_line.redis_vars.clear",
        Mock(side_effect=RuntimeError("stop-after-redis")),
    )

    ctx = Mock()
    with pytest.raises(RuntimeError, match="stop-after-redis"):
        _pre_launch(
            ctx,
            mode="debug",
            archive=None,
            local_=True,
            docker=True,
        )

    ensure.assert_not_called()


def test_pre_launch_ensures_services_for_local_venv_mode(monkeypatch):
    from psynet.command_line import _pre_launch

    ensure = Mock()
    monkeypatch.setattr("psynet.services.ensure_local_services", ensure)
    monkeypatch.setattr(
        "psynet.command_line._check_experiment_directory", lambda mode: None
    )
    monkeypatch.setattr(
        "psynet.command_line.redis_vars.clear",
        Mock(side_effect=RuntimeError("stop-after-redis")),
    )

    ctx = Mock()
    with pytest.raises(RuntimeError, match="stop-after-redis"):
        _pre_launch(
            ctx,
            mode="debug",
            archive=None,
            local_=True,
            docker=False,
        )

    ensure.assert_called_once_with(assume_yes=False, strict=True)


def test_test_local_ensures_services(monkeypatch):
    """``psynet test local`` must ensure Postgres/Redis like local debug/deploy."""
    from psynet.command_line import test__local

    ensure = Mock()
    experiment = Mock()
    monkeypatch.setattr("psynet.services.ensure_local_services", ensure)
    monkeypatch.setattr(
        "psynet.command_line._check_experiment_directory", lambda mode: None
    )
    monkeypatch.setattr(
        "psynet.experiment.get_experiment",
        lambda: experiment,
    )
    monkeypatch.setattr("pytest.main", lambda args: 0)

    result = CliRunner().invoke(test__local, [])
    assert result.exit_code == 0, result.output
    ensure.assert_called_once_with(assume_yes=False, strict=True)
