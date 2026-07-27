"""Identifier separation for exported database snapshots."""

from __future__ import annotations

import csv
import os
import shutil
from typing import Optional

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
        sidecar_rows = []
        for row in rows:
            sidecar_rows.append(
                {
                    "participant_id": row.get("id", ""),
                    "worker_id": row.get("worker_id", ""),
                    "assignment_id": row.get("assignment_id", ""),
                    "hit_id": row.get("hit_id", ""),
                    "unique_id": row.get("unique_id", ""),
                    "client_ip_address": row.get("client_ip_address", ""),
                    "entry_information": row.get("entry_information", ""),
                }
            )
        out = os.path.join(export_path, "participant_identifiers.csv")
        _write_csv(out, list(PARTICIPANT_IDENTIFIER_FIELDS), sidecar_rows)
        paths["participant_identifiers"] = out

    lucid_path = os.path.join(csv_dir, "lucid_rid.csv")
    if os.path.exists(lucid_path):
        _, rows = _read_csv(lucid_path)
        sidecar_rows = []
        for row in rows:
            sidecar_rows.append(
                {
                    "lucid_rid_id": row.get("id", ""),
                    "rid": row.get("rid", ""),
                    "lucid_panelist_id": row.get("lucid_panelist_id", ""),
                    "lucid_respondent_id": row.get("lucid_respondent_id", ""),
                    "participant_id": row.get("participant_id", ""),
                }
            )
        # Include participant_id for join convenience even though it is not a
        # recruiter identifier; keep the documented identifier fields first.
        fieldnames = list(LUCID_ENTRANT_IDENTIFIER_FIELDS) + ["participant_id"]
        # Deduplicate if participant_id somehow appears twice.
        seen = set()
        ordered = []
        for name in fieldnames:
            if name not in seen:
                ordered.append(name)
                seen.add(name)
        out = os.path.join(export_path, "lucid_entrant_identifiers.csv")
        _write_csv(out, ordered, sidecar_rows)
        paths["lucid_entrant_identifiers"] = out

    return paths


def apply_identifier_separation_to_csv_dir(
    raw_dir: str, out_dir: str, table_names: list[str]
) -> None:
    """Copy CSVs to ``out_dir``, rewriting identifier columns to pseudonyms."""
    os.makedirs(out_dir, exist_ok=True)

    unique_id_map: dict[str, str] = {}
    worker_id_map: dict[str, str] = {}
    participant_rows = []
    if os.path.exists(os.path.join(raw_dir, "participant.csv")):
        _, participant_rows = _read_csv(os.path.join(raw_dir, "participant.csv"))
        for row in participant_rows:
            pseudonyms = _participant_pseudonyms(row)
            old_unique = row.get("unique_id", "")
            old_worker = row.get("worker_id", "")
            if old_unique:
                unique_id_map[old_unique] = pseudonyms["unique_id"]
            if old_worker:
                worker_id_map[old_worker] = pseudonyms["worker_id"]

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


def write_identifier_sidecars(
    export_path: str, *, raw_csv_dir: Optional[str] = None
) -> dict:
    """Public helper used when sidecars are written from an existing CSV dir."""
    if raw_csv_dir is None:
        raise ValueError("raw_csv_dir is required")
    return write_identifier_sidecars_from_csv_dir(raw_csv_dir, export_path)
