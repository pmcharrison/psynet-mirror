"""Check and ensure local PostgreSQL and Redis for PsyNet experiments.

Standalone virtualenv workflows expect Postgres and Redis on localhost (the
Dallinger defaults). This module probes those services without mutating Redis
state, and can start Docker containers that publish the host ports PsyNet
debug expects.

Probes intentionally avoid requiring ``psycopg2`` or the ``redis`` package so
the thin bootstrap CLI can keep core dependencies minimal (``click`` /
``yaspin``). Redis is checked with a stdlib RESP ``PING``. PostgreSQL prefers
an installed ``psycopg2`` when present (after ``psynet[experiment]``), otherwise
``pg_isready``, otherwise a TCP port probe.

Docker experiment workflows that use ``docker/run`` manage services on the
``dallinger`` network separately; prefer ``psynet services check`` there
rather than auto-starting host-port containers.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import click

_REDIS_CONTAINER = "dallinger_redis"
_POSTGRES_CONTAINER = "dallinger_postgres"
_READY_WAIT_SECONDS = 30
_READY_POLL_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True)
class ServiceCheck:
    """Result of probing one local service."""

    name: str
    ok: bool
    detail: str


def _postgres_url() -> str:
    """Return the PostgreSQL DSN to probe, honouring ``DATABASE_URL``."""
    return os.environ.get(
        "DATABASE_URL", "postgresql://dallinger:dallinger@localhost/dallinger"
    )


def _redis_url() -> str:
    """Return the Redis URL to probe, honouring ``REDIS_URL``."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


def _host_port_from_url(url: str, *, default_port: int) -> tuple[str, int]:
    """Return ``(host, port)`` from a database/redis URL."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    return host, port


def check_postgres() -> ServiceCheck:
    """Return whether PostgreSQL accepts connections on the configured URL."""
    dsn = _postgres_url()
    try:
        import psycopg2
    except ImportError:
        return _check_postgres_without_psycopg2(dsn)

    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        conn.close()
    except Exception as exc:
        return ServiceCheck(
            "PostgreSQL",
            False,
            str(exc).strip()
            or "Failed to connect to PostgreSQL. Is it running on port 5432?",
        )
    return ServiceCheck("PostgreSQL", True, "reachable")


def _check_postgres_without_psycopg2(dsn: str) -> ServiceCheck:
    """Probe PostgreSQL without the ``psycopg2`` package (thin bootstrap)."""
    host, port = _host_port_from_url(dsn, default_port=5432)
    if shutil.which("pg_isready") is not None:
        result = subprocess.run(
            ["pg_isready", "-h", host, "-p", str(port)],
            capture_output=True,
            text=True,
            check=False,
        )
        detail = (result.stdout or result.stderr or "").strip() or f"{host}:{port}"
        if result.returncode == 0:
            return ServiceCheck("PostgreSQL", True, f"pg_isready: {detail}")
        return ServiceCheck(
            "PostgreSQL",
            False,
            detail or "pg_isready reports PostgreSQL is not accepting connections.",
        )

    try:
        with socket.create_connection((host, port), timeout=3):
            return ServiceCheck(
                "PostgreSQL",
                True,
                f"port {port} open (install psynet[experiment] for a full auth check)",
            )
    except OSError as exc:
        return ServiceCheck(
            "PostgreSQL",
            False,
            str(exc).strip()
            or "Failed to connect to PostgreSQL. Is it running on port 5432?",
        )


def check_redis() -> ServiceCheck:
    """Return whether Redis responds to PING on the configured URL."""
    url = _redis_url()
    host, port = _host_port_from_url(url, default_port=6379)
    try:
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = sock.recv(1024)
    except OSError as exc:
        return ServiceCheck(
            "Redis",
            False,
            f"Failed to connect to Redis ({exc}). Is Redis running on port 6379?",
        )
    if b"PONG" not in response:
        detail = response.decode("utf-8", errors="replace").strip() or repr(response)
        return ServiceCheck(
            "Redis",
            False,
            f"Redis did not respond to PING ({detail}). Is it running on port 6379?",
        )
    return ServiceCheck("Redis", True, "responded to PING")


def check_local_services() -> list[ServiceCheck]:
    """Probe PostgreSQL and Redis and return both results."""
    return [check_postgres(), check_redis()]


def report_service_checks(checks: list[ServiceCheck]) -> bool:
    """Print service check results. Return whether every service is healthy."""
    all_ok = True
    for check in checks:
        if check.ok:
            click.echo(f"  {check.name}: OK ({check.detail})")
        else:
            all_ok = False
            click.echo(f"  {check.name}: unavailable — {check.detail}", err=True)
    return all_ok


def _missing_services_message(checks: list[ServiceCheck]) -> str:
    missing = [check.name for check in checks if not check.ok]
    names = " and ".join(missing)
    return (
        f"{names} must be running for local PsyNet experiments.\n\n"
        "Start them with Docker:\n"
        "  psynet services ensure\n\n"
        "Or install/start PostgreSQL and Redis on this machine, then re-run:\n"
        "  psynet services check"
    )


def docker_available() -> bool:
    """Return whether the Docker CLI is on PATH."""
    return shutil.which("docker") is not None


def _docker_container_exists(name: str) -> bool:
    """Return whether a Docker container with this name exists.

    Scoped to ``docker container inspect`` because bare ``docker inspect``
    also matches volumes, images, and networks. The service volumes reuse
    their container's name, so a bare inspect succeeds when only a leftover
    volume remains and the subsequent ``docker start`` then fails.
    """
    result = subprocess.run(
        ["docker", "container", "inspect", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _docker_container_running(name: str) -> bool:
    """Return whether a Docker container with this name is running."""
    result = subprocess.run(
        ["docker", "container", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _run_docker(args: list[str], *, description: str) -> None:
    try:
        subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise click.ClickException(
            "Could not find docker. Install Docker Desktop (or the Docker CLI) "
            "and try again."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f"\n{detail}" if detail else ""
        raise click.ClickException(f"Failed to {description}.{suffix}") from exc


def _ensure_docker_container(name: str, run_args: list[str]) -> None:
    """Start an existing container or create it with ``run_args``."""
    if _docker_container_running(name):
        click.echo(f"  {name}: already running")
        return
    if _docker_container_exists(name):
        click.echo(f"  Starting existing container {name}...")
        _run_docker(["start", name], description=f"start Docker container {name}")
        return
    click.echo(f"  Creating container {name}...")
    _run_docker(run_args, description=f"create Docker container {name}")


def start_local_services_via_docker() -> None:
    """Start localhost-mapped Postgres/Redis containers used by venv debug."""
    if not docker_available():
        raise click.ClickException(
            "Docker is not available, so PsyNet cannot start PostgreSQL/Redis "
            "for you. Install Docker, or install PostgreSQL and Redis on this "
            "machine, then run 'psynet services check'."
        )

    click.echo("Starting local services with Docker...")
    _ensure_docker_container(
        _REDIS_CONTAINER,
        [
            "run",
            "-d",
            "--name",
            _REDIS_CONTAINER,
            "-p",
            "6379:6379",
            "-v",
            "dallinger_redis:/data",
            "redis",
            "redis-server",
            "--appendonly",
            "yes",
        ],
    )
    _ensure_docker_container(
        _POSTGRES_CONTAINER,
        [
            "run",
            "-d",
            "--name",
            _POSTGRES_CONTAINER,
            "-p",
            "5432:5432",
            "-e",
            "POSTGRES_USER=dallinger",
            "-e",
            "POSTGRES_PASSWORD=dallinger",
            "-e",
            "POSTGRES_DB=dallinger",
            "-v",
            "dallinger_postgres:/var/lib/postgresql/data",
            "postgres:12",
        ],
    )


def _wait_until_services_ready(
    timeout_seconds: float = _READY_WAIT_SECONDS,
) -> list[ServiceCheck]:
    """Poll until services are healthy or ``timeout_seconds`` elapses."""
    deadline = time.monotonic() + timeout_seconds
    checks = check_local_services()
    while not all(check.ok for check in checks) and time.monotonic() < deadline:
        time.sleep(_READY_POLL_INTERVAL_SECONDS)
        checks = check_local_services()
    return checks


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def verify_local_services(*, strict: bool) -> bool:
    """Check local services without attempting to start them.

    Parameters
    ----------
    strict :
        If True, raise ``click.ClickException`` when any service is missing.
    """
    click.echo("Checking local PostgreSQL and Redis...")
    checks = check_local_services()
    all_ok = report_service_checks(checks)
    if all_ok:
        return True
    message = _missing_services_message(checks)
    if strict:
        raise click.ClickException(message)
    click.echo(f"Warning: {message}", err=True)
    return False


def ensure_local_services(*, assume_yes: bool = False, strict: bool = True) -> bool:
    """Check local services and optionally start them with Docker.

    Parameters
    ----------
    assume_yes :
        If True, start Docker services without prompting when needed.
    strict :
        If True, raise when services remain unavailable after any start attempt.
    """
    click.echo("Checking local PostgreSQL and Redis...")
    checks = check_local_services()
    all_ok = report_service_checks(checks)
    if all_ok:
        return True

    if not assume_yes:
        if not _is_interactive():
            message = (
                _missing_services_message(checks)
                + "\n\nNon-interactive session: re-run with "
                "'psynet services ensure --yes' to start Docker services "
                "without prompting."
            )
            if strict:
                raise click.ClickException(message)
            click.echo(f"Warning: {message}", err=True)
            return False
        if not click.confirm(
            "Start PostgreSQL and Redis with Docker now?",
            default=True,
        ):
            message = _missing_services_message(checks)
            if strict:
                raise click.ClickException(message)
            click.echo(f"Warning: {message}", err=True)
            return False

    try:
        start_local_services_via_docker()
    except click.ClickException as exc:
        if strict:
            raise
        click.echo(f"Warning: {exc}", err=True)
        return False

    click.echo("Waiting for services to become ready...")
    checks = _wait_until_services_ready()
    all_ok = report_service_checks(checks)
    if all_ok:
        click.echo("Local services are ready.")
        return True

    message = (
        "Started Docker containers, but services are still unreachable.\n"
        "If port 5432 or 6379 is already used by another install, stop that "
        "service or point PsyNet/Dallinger at the correct URLs.\n\n"
        + _missing_services_message(checks)
    )
    if strict:
        raise click.ClickException(message)
    click.echo(f"Warning: {message}", err=True)
    return False
