"""Identifier separation for exported database snapshots.

Live tables keep recruiter identifiers on ``Participant`` (and Lucid ghost
entrants). Export writes those values to sidecar CSVs and replaces them with
participant-id pseudonyms in ``database/`` so the archive remains loadable.
``participant.entry_information`` is written as ``{}`` rather than left blank,
because that column is NOT NULL. Copied tables that still carry recruiter
columns (``worker_id``, ``assignment_id``, ``unique_id``, ``hit_id``,
``client_ip_address``, ``entry_information``) are remapped or blanked the same
way.
"""

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
        # Empty JSON object, not a blank field: participant.entry_information
        # is NOT NULL, so a loadable archive cannot use COPY's NULL.
        "entry_information": "{}",
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
    worker_id_map: dict[str, str] = {}
    assignment_id_map: dict[str, str] = {}
    if os.path.exists(os.path.join(raw_dir, "participant.csv")):
        _, participant_rows = _read_csv(os.path.join(raw_dir, "participant.csv"))
        for row in participant_rows:
            pseudonyms = _participant_pseudonyms(row)
            old_unique = row.get("unique_id", "")
            if old_unique:
                unique_id_map[old_unique] = pseudonyms["unique_id"]
            old_worker = row.get("worker_id", "")
            if old_worker:
                worker_id_map[old_worker] = pseudonyms["worker_id"]
            old_assignment = row.get("assignment_id", "")
            if old_assignment:
                assignment_id_map[old_assignment] = pseudonyms["assignment_id"]

    maps = {
        "unique_id": unique_id_map,
        "worker_id": worker_id_map,
        "assignment_id": assignment_id_map,
    }

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

        fieldnames, rows = _read_csv(src)
        if not _table_needs_identifier_rewrite(table, fieldnames):
            shutil.copyfile(src, dst)
            continue

        rewritten = [
            _rewrite_copied_row(row, maps, blank_params=(table == "request"))
            for row in rows
        ]
        _write_csv(dst, fieldnames, rewritten)


_COPIED_IDENTIFIER_MAP_FIELDS = ("unique_id", "worker_id", "assignment_id")
_COPIED_IDENTIFIER_BLANK_FIELDS = (
    "client_ip_address",
    "entry_information",
    "hit_id",
)


def _table_needs_identifier_rewrite(table: str, fieldnames: list[str]) -> bool:
    """Return True when a copied table has recruiter identifiers or request params."""
    if table == "request":
        return True
    names = set(fieldnames)
    return any(
        name in names
        for name in _COPIED_IDENTIFIER_MAP_FIELDS + _COPIED_IDENTIFIER_BLANK_FIELDS
    )


def _rewrite_copied_row(
    row: dict, maps: dict[str, dict[str, str]], *, blank_params: bool
) -> dict:
    """Replace recruiter identifiers on a non-participant, non-Lucid row."""
    row = dict(row)
    for field in _COPIED_IDENTIFIER_BLANK_FIELDS:
        if field in row:
            row[field] = ""
    for field in _COPIED_IDENTIFIER_MAP_FIELDS:
        if field not in row:
            continue
        old = row.get(field) or ""
        if not old:
            continue
        row[field] = maps.get(field, {}).get(old, "")
    if blank_params and "params" in row:
        row["params"] = ""
    return row
