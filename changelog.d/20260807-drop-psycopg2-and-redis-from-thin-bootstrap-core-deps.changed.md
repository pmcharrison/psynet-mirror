Removed ``psycopg2-binary`` and ``redis`` from PsyNet's core bootstrap
dependencies. ``psynet services`` now probes Redis with a stdlib RESP
``PING`` and PostgreSQL via ``psycopg2`` when available, otherwise
``pg_isready`` or a TCP port check.
