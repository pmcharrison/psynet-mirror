"""Tests for the canonical PsyNet export package."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from psynet.export.analysis import (
    load_export_table,
    merge_participant_identifiers,
    unpack_json_column,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_analysis_helpers_round_trip(tmp_path):
    # Legacy zip layout still loads.
    database_zip = tmp_path / "legacy.zip"
    with zipfile.ZipFile(database_zip, "w") as archive:
        archive.writestr(
            "data/trial.csv",
            'id,definition\n1,"{""animal"": ""cat""}"\n',
        )

    trials = load_export_table(str(database_zip), "trial")
    unpacked = unpack_json_column(trials, "definition")
    assert unpacked.iloc[0]["animal"] == "cat"

    # Flat database/ directory.
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "trial.csv").write_text(
        'id,definition\n2,"{""animal"": ""dog""}"\n'
    )
    trials = load_export_table(str(database_dir), "trial")
    assert unpack_json_column(trials, "definition").iloc[0]["animal"] == "dog"

    # Extracted export directory containing database/.
    export_dir = tmp_path / "export"
    nested = export_dir / "database"
    nested.mkdir(parents=True)
    (nested / "trial.csv").write_text('id,definition\n3,"{""animal"": ""bird""}"\n')
    trials = load_export_table(str(export_dir), "trial")
    assert unpack_json_column(trials, "definition").iloc[0]["animal"] == "bird"

    # New export.zip layout.
    export_zip = tmp_path / "export.zip"
    with zipfile.ZipFile(export_zip, "w") as archive:
        archive.writestr(
            "database/trial.csv",
            'id,definition\n4,"{""animal"": ""fish""}"\n',
        )
    trials = load_export_table(str(export_zip), "trial")
    assert unpack_json_column(trials, "definition").iloc[0]["animal"] == "fish"

    identifiers = pd.DataFrame([{"participant_id": 1, "worker_id": "worker-1"}])
    frame = pd.DataFrame([{"participant_id": 1, "score": 3}])
    merged = merge_participant_identifiers(frame, identifiers)
    assert merged.iloc[0]["worker_id"] == "worker-1"


def test_analysis_helpers_accept_path_objects(tmp_path):
    database = tmp_path / "database"
    database.mkdir()
    (database / "trial.csv").write_text("id,participant_id\n1,1\n")
    identifiers = tmp_path / "participant_identifiers.csv"
    identifiers.write_text("participant_id,worker_id\n1,worker-1\n")

    trials = load_export_table(tmp_path, "trial")
    merged = merge_participant_identifiers(trials, identifiers)
    assert merged.iloc[0]["worker_id"] == "worker-1"


def test_ingest_zip_skips_tables_without_csv_files(tmp_path, monkeypatch):
    from psynet.data import ingest_zip

    export_dir = tmp_path / "export"
    csv_dir = export_dir / "database"
    csv_dir.mkdir(parents=True)
    (csv_dir / "trial.csv").write_text("id\n1\n")

    ingested = []

    class _Inspector:
        def get_table_names(self):
            return ["trial", "chat_message"]

    monkeypatch.setattr("psynet.data.sqlalchemy.inspect", lambda engine: _Inspector())
    monkeypatch.setattr(
        "psynet.data.sql_base_classes",
        lambda: {
            "trial": type("Trial", (), {"__tablename__": "trial"}),
            "chat_message": type("ChatMessage", (), {"__tablename__": "chat_message"}),
        },
    )
    monkeypatch.setattr(
        "psynet.data.ingest_to_model",
        lambda file, model, engine: ingested.append(model.__tablename__),
    )

    ingest_zip(str(export_dir), engine=object())
    assert ingested == ["trial"]


def test_archive_template_only_packs_present_table_csvs(tmp_path):
    from psynet.command_line import _install_archive_template

    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "trial.csv").write_text("id\n1\n")
    archive = tmp_path / "database_template.zip"

    _install_archive_template(str(tmp_path), str(archive))

    with zipfile.ZipFile(archive) as handle:
        assert handle.namelist() == ["database/trial.csv"]


def test_archive_template_keeps_only_table_csvs_from_a_zip(tmp_path):
    """An export.zip is deployed to the server, so sidecars must not travel."""
    from psynet.command_line import _install_archive_template

    export_zip = tmp_path / "export.zip"
    with zipfile.ZipFile(export_zip, "w") as archive:
        archive.writestr("database/trial.csv", "id\n1\n")
        archive.writestr(
            "participant_identifiers.csv", "participant_id,worker_id\n1,w\n"
        )
        archive.writestr("assets/manifest.csv", "id\n1\n")
        archive.writestr("manifest.json", "{}")

    template = tmp_path / "database_template.zip"
    _install_archive_template(str(export_zip), str(template))

    with zipfile.ZipFile(template) as handle:
        assert handle.namelist() == ["database/trial.csv"]


def test_load_export_table_parses_copy_and_python_booleans(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    (database_dir / "network.csv").write_text(
        "id,failed,complete\n1,t,True\n2,f,False\n"
    )
    networks = load_export_table(str(database_dir), "network")
    assert list(networks.failed) == [True, False]
    assert list(networks.complete) == [True, False]


def test_empty_table_csvs_are_omitted_from_the_export(tmp_path, monkeypatch):
    from psynet.export.database import omit_empty_table_csvs, write_export_manifest

    csv_dir = tmp_path / "database"
    csv_dir.mkdir()
    (csv_dir / "trial.csv").write_text("id\n1\n")
    (csv_dir / "chat_message.csv").write_text("id,body\n")

    omit_empty_table_csvs(str(csv_dir), ["trial", "chat_message"])

    assert (csv_dir / "trial.csv").exists()
    assert not (csv_dir / "chat_message.csv").exists()

    experiment = Mock()
    experiment.deployment_id = "demo__export"
    experiment.label = "demo"
    experiment.var.get.return_value = None
    monkeypatch.setattr("psynet.experiment.get_experiment", lambda: experiment)

    manifest = json.loads(
        Path(
            write_export_manifest(
                str(tmp_path),
                table_names=["trial", "chat_message"],
                csv_dir=str(csv_dir),
            )
        ).read_text()
    )
    assert "database/trial.csv" in manifest["files"]
    assert "database/chat_message.csv" not in manifest["files"]
    assert manifest["table_row_counts"]["trial"] == 1
    assert manifest["table_row_counts"]["chat_message"] == 0


def test_write_export_manifest_records_git_provenance(tmp_path, monkeypatch):
    from psynet.export.database import write_export_manifest

    csv_dir = tmp_path / "database"
    csv_dir.mkdir()
    (csv_dir / "trial.csv").write_text("id\n1\n")

    experiment = Mock()
    experiment.deployment_id = "demo__export"
    experiment.label = "demo"
    experiment.var.get.side_effect = lambda name, default=None: {
        "git_commit_sha": "abc123def",
        "git_dirty": True,
    }.get(name, default)
    monkeypatch.setattr("psynet.experiment.get_experiment", lambda: experiment)

    manifest_path = write_export_manifest(
        str(tmp_path),
        table_names=["trial"],
        csv_dir=str(csv_dir),
    )
    manifest = json.loads(Path(manifest_path).read_text())
    assert manifest["git_commit_sha"] == "abc123def"
    assert manifest["git_dirty"] is True
    assert manifest["deployment_id"] == "demo__export"
    assert manifest["experiment_label"] == "demo"
    assert "source_code.zip" not in manifest.get("files", {})


def test_write_export_manifest_allows_missing_git_provenance(tmp_path, monkeypatch):
    from psynet.export.database import write_export_manifest

    csv_dir = tmp_path / "database"
    csv_dir.mkdir()
    (csv_dir / "trial.csv").write_text("id\n")

    monkeypatch.setattr(
        "psynet.experiment.get_experiment",
        Mock(side_effect=RuntimeError("no experiment")),
    )
    monkeypatch.setattr("psynet.deployment_info.is_available", lambda: False)

    manifest_path = write_export_manifest(
        str(tmp_path),
        table_names=["trial"],
        csv_dir=str(csv_dir),
    )
    manifest = json.loads(Path(manifest_path).read_text())
    assert manifest["git_commit_sha"] is None
    assert manifest["git_dirty"] is None


def test_unpack_json_column_does_not_overwrite_unless_requested():
    frame = pd.DataFrame([{"definition": '{"animal": "cat"}', "animal": "dog"}])
    kept = unpack_json_column(frame, "definition")
    assert kept.iloc[0]["animal"] == "dog"
    overwritten = unpack_json_column(frame, "definition", overwrite=True)
    assert overwritten.iloc[0]["animal"] == "cat"
