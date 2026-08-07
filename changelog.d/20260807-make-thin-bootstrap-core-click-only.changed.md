Removed ``psycopg2-binary``, ``redis``, and ``yaspin`` from PsyNet's core
bootstrap dependencies (now ``click`` only). ``psynet services`` probes Redis
with a stdlib RESP ``PING`` and PostgreSQL via ``psycopg2`` when available,
otherwise ``pg_isready`` or a TCP port check. Version-check spinners still use
``yaspin`` via a lazy import under ``psynet[experiment]``.
