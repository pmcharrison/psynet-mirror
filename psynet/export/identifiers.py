"""Identifier separation for exported database snapshots."""

from __future__ import annotations

import csv
import os
import shutil

from psynet.identifiers import (
    LUCID_ENTRANT_IDENTIFIER_FIELDS,
    PARTICIPANT_IDENTIFIER_FIELDS,
)
from psynet.utils import make_parents


def _read_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return fieldnames, rows


def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    make_parents(path)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _participant_pseudonyms(row: dict) -> dict:
    participant_id = row["id"]
    assignment_pseudo = str(participant_id)
    return {
        "worker_id": str(participant_id),
        "assignment_id": assignment_pseudo,
        "hit_id": str(participant_id),
        "unique_id": f"{participant_id}:{assignment_pseudo}",
        "client_ip_address": "",
        "entry_information": "",
    }


def write_identifier_sidecars_from_csv_dir(csv_dir: str, export_path: str) -> dict:
    """Write participant and Lucid entrant identifier sidecars from raw CSVs."""
    paths = {}

    participant_path = os.path.join(csv_dir, "participant.csv")
    if os.path.exists(participant_path):
        _, rows = _read_csv(participant_path)
        sidecar_rows = [_participant_sidecar_row(row) for row in rows]
        out = os.path.join(export_path, "participant_identifiers.csv")
        _write_csv(out, list(PARTICIPANT_IDENTIFIER_FIELDS), sidecar_rows)
        paths["participant_identifiers"] = out

    lucid_path = os.path.join(csv_dir, "lucid_rid.csv")
    if os.path.exists(lucid_path):
        _, rows = _read_csv(lucid_path)
        if rows:
            # Include participant_id for join convenience even though it is not
            # a recruiter identifier; keep documented identifier fields first.
            ordered = list(LUCID_ENTRANT_IDENTIFIER_FIELDS) + ["participant_id"]
            sidecar_rows = [_lucid_sidecar_row(row) for row in rows]
            out = os.path.join(export_path, "lucid_entrant_identifiers.csv")
            _write_csv(out, ordered, sidecar_rows)
            paths["lucid_entrant_identifiers"] = out

    return paths


def _participant_sidecar_row(row: dict) -> dict:
    """Build one participant sidecar row from a participant CSV row."""
    out = {}
    for field in PARTICIPANT_IDENTIFIER_FIELDS:
        if field == "participant_id":
            out[field] = row.get("id", "")
        else:
            out[field] = row.get(field, "")
    return out


def _lucid_sidecar_row(row: dict) -> dict:
    """Build one Lucid entrant sidecar row from a lucid_rid CSV row."""
    out = {}
    for field in LUCID_ENTRANT_IDENTIFIER_FIELDS:
        if field == "lucid_rid_id":
            out[field] = row.get("id", "")
        else:
            out[field] = row.get(field, "")
    out["participant_id"] = row.get("participant_id", "")
    return out


def apply_identifier_separation_to_csv_dir(
    raw_dir: str, out_dir: str, table_names: list[str]
) -> None:
    """Copy CSVs to ``out_dir``, rewriting identifier columns to pseudonyms."""
    os.makedirs(out_dir, exist_ok=True)

    unique_id_map: dict[str, str] = {}
    participant_rows = []
    if os.path.exists(os.path.join(raw_dir, "participant.csv")):
        _, participant_rows = _read_csv(os.path.join(raw_dir, "participant.csv"))
        for row in participant_rows:
            pseudonyms = _participant_pseudonyms(row)
            old_unique = row.get("unique_id", "")
            if old_unique:
                unique_id_map[old_unique] = pseudonyms["unique_id"]

    for table in table_names:
        src = os.path.join(raw_dir, f"{table}.csv")
        dst = os.path.join(out_dir, f"{table}.csv")
        if not os.path.exists(src):
            continue

        if table == "participant":
            fieldnames, rows = _read_csv(src)
            rewritten = []
            for row in rows:
                row = dict(row)
                row.update(_participant_pseudonyms(row))
                rewritten.append(row)
            _write_csv(dst, fieldnames, rewritten)
            continue

        if table == "request":
            fieldnames, rows = _read_csv(src)
            rewritten = []
            for row in rows:
                row = dict(row)
                old_unique = row.get("unique_id", "")
                if old_unique in unique_id_map:
                    row["unique_id"] = unique_id_map[old_unique]
                # Request params can contain recruiter identifiers.
                if "params" in row:
                    row["params"] = ""
                rewritten.append(row)
            _write_csv(dst, fieldnames, rewritten)
            continue

        if table == "lucid_rid":
            fieldnames, rows = _read_csv(src)
            rewritten = []
            for row in rows:
                row = dict(row)
                participant_id = row.get("participant_id") or ""
                lucid_id = row.get("id") or ""
                if participant_id:
                    row["rid"] = str(participant_id)
                else:
                    row["rid"] = f"entrant-{lucid_id}"
                row["lucid_panelist_id"] = ""
                row["lucid_respondent_id"] = ""
                rewritten.append(row)
            _write_csv(dst, fieldnames, rewritten)
            continue

        shutil.copyfile(src, dst)
