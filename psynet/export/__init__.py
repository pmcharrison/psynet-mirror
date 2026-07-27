"""Canonical PsyNet export: database snapshot, identifier sidecars, and analysis helpers.

The shareable database archive uses pseudonymous participant identifiers.
Original recruiter identifiers are written beside the archive in sidecar CSV
files. This is identifier separation, not anonymization.
"""

from .analysis import (
    load_export_table,
    merge_participant_identifiers,
    unpack_json_column,
)
from .database import export_database_snapshot
from .identifiers import write_identifier_sidecars

__all__ = [
    "export_database_snapshot",
    "load_export_table",
    "merge_participant_identifiers",
    "unpack_json_column",
    "write_identifier_sidecars",
]
