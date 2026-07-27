Changed database export to a single PostgreSQL ``COPY`` snapshot with identifier separation.

``database.zip`` now contains physical table CSVs with pseudonymous participant
identifiers. Original recruiter identifiers are written to
``participant_identifiers.csv`` (and ``lucid_entrant_identifiers.csv`` for Lucid).
The ``--anonymize`` flag and class-based ORM CSV export have been removed. Analysis
helpers ``load_export_table``, ``unpack_json_column``, and
``merge_participant_identifiers`` are provided under ``psynet.export``. The
``extra_var`` registry and implicit VarStore flattening have been removed; runtime
properties created with ``claim_var`` are preserved. VarStore values remain in the
physical ``vars`` column and can be unpacked with ``unpack_json_column``. Selected
assets are always exported when requested.
