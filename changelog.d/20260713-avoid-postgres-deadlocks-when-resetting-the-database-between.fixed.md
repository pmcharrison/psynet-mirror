Fixed intermittent Postgres deadlocks in CI when resetting the database between experiment tests, by terminating stale database connections before dropping tables and retrying on deadlock.
