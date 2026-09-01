Exported ``database/participant.csv`` now writes ``{}`` for ``entry_information`` instead of a blank field, so ``psynet load`` and ``--archive`` no longer fail the NOT NULL constraint.
