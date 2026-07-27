Removed duplicated participant identifiers from ``ErrorRecord`` and ``Response``,
and linked ``LucidRID`` to participants via nullable ``participant_id`` instead of
a foreign key on ``worker_id``.
