Added a scheduled finalize backstop that recovers trials whose event-driven finalize check was missed, with a partial index and SQL prefilters so the poller stays cheap in steady state.
