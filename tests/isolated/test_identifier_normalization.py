"""Identifier ownership lives on Participant (and LucidRID for ghosts)."""

from sqlalchemy import inspect as sa_inspect

from psynet.error import ErrorRecord
from psynet.identifiers import (
    LUCID_ENTRANT_IDENTIFIER_FIELDS,
    PARTICIPANT_IDENTIFIER_FIELDS,
)
from psynet.recruiters import LucidRID
from psynet.timeline import Response


def test_participant_identifier_fields():
    assert PARTICIPANT_IDENTIFIER_FIELDS == (
        "participant_id",
        "worker_id",
        "assignment_id",
        "hit_id",
        "unique_id",
        "client_ip_address",
        "entry_information",
    )


def test_lucid_entrant_identifier_fields():
    assert LUCID_ENTRANT_IDENTIFIER_FIELDS == (
        "lucid_rid_id",
        "rid",
        "lucid_panelist_id",
        "lucid_respondent_id",
    )


def test_error_record_has_no_worker_id_column():
    columns = {c.key for c in sa_inspect(ErrorRecord).columns}
    assert "worker_id" not in columns
    assert "participant_id" in columns


def test_response_has_no_client_ip_column():
    columns = {c.key for c in sa_inspect(Response).columns}
    assert "client_ip_address" not in columns
    assert "participant_id" in columns


def test_lucid_rid_uses_participant_id_fk():
    columns = {c.key: c for c in sa_inspect(LucidRID).columns}
    assert "participant_id" in columns
    assert "rid" in columns
    rid_fks = list(columns["rid"].foreign_keys)
    assert rid_fks == []
    participant_fks = list(columns["participant_id"].foreign_keys)
    assert len(participant_fks) == 1
    assert participant_fks[0].column.table.name == "participant"
