"""Tests for the canonical PsyNet export package."""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

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

    sidecars = write_identifier_sidecars_from_csv_dir(str(raw_dir), str(export_path))
    apply_identifier_separation_to_csv_dir(
        str(raw_dir),
        str(out_dir),
        ["participant", "request", "lucid_rid", "trial"],
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


def test_analysis_helpers_round_trip(tmp_path):
    database_zip = tmp_path / "database.zip"
    with zipfile.ZipFile(database_zip, "w") as archive:
        archive.writestr(
            "data/trial.csv",
            'id,definition\n1,"{""animal"": ""cat""}"\n',
        )

    trials = load_export_table(str(database_zip), "trial")
    unpacked = unpack_json_column(trials, "definition")
    assert unpacked.iloc[0]["animal"] == "cat"

    identifiers = pd.DataFrame([{"participant_id": 1, "worker_id": "worker-1"}])
    frame = pd.DataFrame([{"participant_id": 1, "score": 3}])
    merged = merge_participant_identifiers(frame, identifiers)
    assert merged.iloc[0]["worker_id"] == "worker-1"


def test_unpack_json_column_does_not_overwrite_unless_requested():
    frame = pd.DataFrame([{"definition": '{"animal": "cat"}', "animal": "dog"}])
    kept = unpack_json_column(frame, "definition")
    assert kept.iloc[0]["animal"] == "dog"
    overwritten = unpack_json_column(frame, "definition", overwrite=True)
    assert overwritten.iloc[0]["animal"] == "cat"
