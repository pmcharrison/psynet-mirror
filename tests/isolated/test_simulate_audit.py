"""Isolated tests for ``psynet simulate --audit`` packaging."""

from pathlib import Path
from zipfile import ZipFile

import click
import pytest


def _write_export_tree(root: Path) -> Path:
    export_dir = root / "data" / "simulated_data"
    csv_dir = export_dir / "regular" / "data"
    csv_dir.mkdir(parents=True)
    (csv_dir / "AnimalTrial.csv").write_text("id\n1\n", encoding="utf-8")
    return export_dir


def test_resolve_audit_artifact_path_creates_artifacts(tmp_path):
    from psynet.command_line import (
        AUDIT_SIMULATED_DATA_ZIP,
        resolve_audit_artifact_path,
    )

    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    (audit_dir / "audit.json").write_text("{}", encoding="utf-8")

    resolved = resolve_audit_artifact_path(audit_dir, AUDIT_SIMULATED_DATA_ZIP)
    assert resolved == audit_dir / "artifacts" / "simulated_data.zip"
    assert (audit_dir / "artifacts").is_dir()


def test_resolve_audit_artifact_path_autodetects_nested_audit(tmp_path, monkeypatch):
    from psynet.command_line import (
        AUDIT_SIMULATED_DATA_ZIP,
        resolve_audit_artifact_path,
    )

    experiment = tmp_path / "exp"
    audit_dir = experiment / "audit"
    audit_dir.mkdir(parents=True)
    (audit_dir / "audit.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(experiment)

    resolved = resolve_audit_artifact_path(Path("."), AUDIT_SIMULATED_DATA_ZIP)
    assert (
        resolved.resolve() == (audit_dir / "artifacts" / "simulated_data.zip").resolve()
    )


def test_write_directory_zip_preserves_data_prefix(tmp_path, monkeypatch):
    from psynet.command_line import write_directory_zip

    monkeypatch.chdir(tmp_path)
    export_dir = _write_export_tree(tmp_path)
    zip_path = tmp_path / "out" / "simulated_data.zip"

    write_directory_zip(export_dir, zip_path)

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "data/simulated_data/regular/data/AnimalTrial.csv" in names


def test_write_directory_zip_overwrites_existing_archive(tmp_path, monkeypatch):
    from psynet.command_line import write_directory_zip

    monkeypatch.chdir(tmp_path)
    export_dir = _write_export_tree(tmp_path)
    zip_path = tmp_path / "simulated_data.zip"
    zip_path.write_bytes(b"stale")

    write_directory_zip(export_dir, zip_path)

    with ZipFile(zip_path) as archive:
        assert "data/simulated_data/regular/data/AnimalTrial.csv" in archive.namelist()


def test_write_directory_zip_requires_directory(tmp_path):
    from psynet.command_line import write_directory_zip

    with pytest.raises(click.UsageError, match="is not a directory"):
        write_directory_zip(tmp_path / "missing", tmp_path / "out.zip")


def test_run_simulate_without_audit_does_not_zip(tmp_path, monkeypatch):
    from psynet.command_line import (
        _run_simulate,
        export__local,
        test__local,
    )

    monkeypatch.chdir(tmp_path)
    calls = []

    class DummyCtx:
        def invoke(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd is export__local:
                _write_export_tree(tmp_path)

    _run_simulate(DummyCtx(), audit=None)

    assert [cmd for cmd, _ in calls] == [test__local, export__local]
    assert not list(tmp_path.glob("**/*.zip"))


def test_run_simulate_audit_zips_export(tmp_path, monkeypatch):
    from psynet.command_line import _run_simulate, export__local

    experiment = tmp_path / "exp"
    audit_dir = experiment / "audit"
    audit_dir.mkdir(parents=True)
    (audit_dir / "audit.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(experiment)

    class DummyCtx:
        def invoke(self, cmd, **kwargs):
            if cmd is export__local:
                _write_export_tree(experiment)

    _run_simulate(DummyCtx(), audit=Path("."))

    zip_path = audit_dir / "artifacts" / "simulated_data.zip"
    assert zip_path.is_file()
    with ZipFile(zip_path) as archive:
        assert "data/simulated_data/regular/data/AnimalTrial.csv" in archive.namelist()
    assert (
        experiment / "data" / "simulated_data" / "regular" / "data" / "AnimalTrial.csv"
    ).is_file()


def test_simulate_help_documents_audit_option():
    from click.testing import CliRunner

    from psynet.command_line import simulate

    result = CliRunner().invoke(simulate, ["--help"])
    assert result.exit_code == 0
    assert "--audit" in result.output
    assert "simulated_data.zip" in result.output
