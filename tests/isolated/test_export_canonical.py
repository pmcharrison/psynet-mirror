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
from psynet.export.identifiers import (
    apply_identifier_separation_to_csv_dir,
    write_identifier_sidecars_from_csv_dir,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_identifier_separation_writes_sidecars_and_pseudonyms(tmp_path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    export_path = tmp_path / "export"
    export_path.mkdir()

    _write_csv(
        raw_dir / "participant.csv",
        [
            "id",
            "worker_id",
            "assignment_id",
            "hit_id",
            "unique_id",
            "client_ip_address",
            "entry_information",
        ],
        [
            {
                "id": "7",
                "worker_id": "worker-abc",
                "assignment_id": "assignment-1",
                "hit_id": "hit-1",
                "unique_id": "worker-abc:assignment-1",
                "client_ip_address": "1.2.3.4",
                "entry_information": '{"email": "a@b.c"}',
            }
        ],
    )
    _write_csv(
        raw_dir / "request.csv",
        ["id", "unique_id", "params"],
        [{"id": "1", "unique_id": "worker-abc:assignment-1", "params": "secret"}],
    )
    _write_csv(
        raw_dir / "lucid_rid.csv",
        [
            "id",
            "rid",
            "lucid_panelist_id",
            "lucid_respondent_id",
            "participant_id",
        ],
        [
            {
                "id": "3",
                "rid": "lucid-rid",
                "lucid_panelist_id": "panel-1",
                "lucid_respondent_id": "resp-1",
                "participant_id": "7",
            },
            {
                "id": "4",
                "rid": "ghost-rid",
                "lucid_panelist_id": "panel-2",
                "lucid_respondent_id": "resp-2",
                "participant_id": "",
            },
        ],
    )
    _write_csv(
        raw_dir / "trial.csv",
        ["id", "participant_id"],
        [{"id": "1", "participant_id": "7"}],
    )
    _write_csv(
        raw_dir / "notification.csv",
        ["id", "assignment_id", "event_type"],
        [
            {
                "id": "1",
                "assignment_id": "assignment-1",
                "event_type": "AssignmentAccepted",
            },
            {
                "id": "2",
                "assignment_id": "unknown-assignment",
                "event_type": "AssignmentAbandoned",
            },
        ],
    )
    _write_csv(
        raw_dir / "response.csv",
        ["id", "participant_id", "client_ip_address"],
        [{"id": "1", "participant_id": "7", "client_ip_address": "9.9.9.9"}],
    )

    sidecars = write_identifier_sidecars_from_csv_dir(str(raw_dir), str(export_path))
    apply_identifier_separation_to_csv_dir(
        str(raw_dir),
        str(out_dir),
        ["participant", "request", "lucid_rid", "trial", "notification", "response"],
    )

    participant_sidecar = pd.read_csv(sidecars["participant_identifiers"])
    assert list(participant_sidecar.columns) == [
        "participant_id",
        "worker_id",
        "assignment_id",
        "hit_id",
        "unique_id",
        "client_ip_address",
        "entry_information",
    ]
    assert participant_sidecar.iloc[0]["worker_id"] == "worker-abc"
    assert participant_sidecar.iloc[0]["entry_information"] == '{"email": "a@b.c"}'

    lucid_sidecar = pd.read_csv(sidecars["lucid_entrant_identifiers"])
    assert lucid_sidecar.shape[0] == 2
    assert set(lucid_sidecar["rid"]) == {"lucid-rid", "ghost-rid"}

    participant = pd.read_csv(out_dir / "participant.csv")
    row = participant.iloc[0]
    assert str(row["worker_id"]) == "7"
    assert str(row["assignment_id"]) == "7"
    assert str(row["hit_id"]) == "7"
    assert row["unique_id"] == "7:7"
    assert pd.isna(row["client_ip_address"]) or row["client_ip_address"] == ""
    assert pd.isna(row["entry_information"]) or row["entry_information"] == ""

    request = pd.read_csv(out_dir / "request.csv")
    assert request.iloc[0]["unique_id"] == "7:7"
    assert pd.isna(request.iloc[0]["params"]) or request.iloc[0]["params"] == ""

    lucid = pd.read_csv(out_dir / "lucid_rid.csv")
    linked = lucid.set_index("id").loc[3]
    ghost = lucid.set_index("id").loc[4]
    assert str(linked["rid"]) == "7"
    assert ghost["rid"] == "entrant-4"
    assert pd.isna(linked["lucid_panelist_id"]) or linked["lucid_panelist_id"] == ""

    trial = pd.read_csv(out_dir / "trial.csv")
    assert trial.iloc[0]["participant_id"] == 7

    notification = pd.read_csv(out_dir / "notification.csv")
    accepted = notification.set_index("id").loc[1]
    abandoned = notification.set_index("id").loc[2]
    assert str(int(accepted["assignment_id"])) == "7"
    assert pd.isna(abandoned["assignment_id"]) or abandoned["assignment_id"] == ""

    response = pd.read_csv(out_dir / "response.csv")
    assert (
        pd.isna(response.iloc[0]["client_ip_address"])
        or response.iloc[0]["client_ip_address"] == ""
    )


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


def test_empty_lucid_table_omits_sidecar(tmp_path):
    raw_dir = tmp_path / "raw"
    export_path = tmp_path / "export"
    export_path.mkdir()
    _write_csv(
        raw_dir / "lucid_rid.csv",
        [
            "id",
            "rid",
            "lucid_panelist_id",
            "lucid_respondent_id",
            "participant_id",
        ],
        [],
    )
    sidecars = write_identifier_sidecars_from_csv_dir(str(raw_dir), str(export_path))
    assert "lucid_entrant_identifiers" not in sidecars
    assert not (export_path / "lucid_entrant_identifiers.csv").exists()


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
