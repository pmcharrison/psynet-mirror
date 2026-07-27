"""Canonical PsyNet export: database snapshot, identifier sidecars, and analysis helpers.

The shareable database archive uses pseudonymous participant identifiers.
Original recruiter identifiers are written beside the archive in sidecar CSV
files. This is identifier separation, not anonymization.

Asset cache
-----------
:mod:`psynet.export.asset_cache` implements a persistent local cache at
``~/psynet-data/cache/assets`` that stores content-addressed objects in
the same ``objects/sha256/<digest>`` layout used in export archives.
"""

from .analysis import (
    load_export_table,
    merge_participant_identifiers,
    unpack_json_column,
)
from .asset_cache import (
    cache_size_bytes,
    default_cache_root,
    ensure_object_in_cache,
    link_or_copy,
    list_cached_objects,
    object_cache_path,
    prune_cached_objects,
)
from .database import export_database_snapshot
from .identifiers import write_identifier_sidecars

__all__ = [
    "cache_size_bytes",
    "default_cache_root",
    "ensure_object_in_cache",
    "export_database_snapshot",
    "link_or_copy",
    "list_cached_objects",
    "load_export_table",
    "merge_participant_identifiers",
    "object_cache_path",
    "prune_cached_objects",
    "unpack_json_column",
    "write_identifier_sidecars",
]
