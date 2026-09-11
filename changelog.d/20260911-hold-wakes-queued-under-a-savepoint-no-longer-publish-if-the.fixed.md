Hold wakes queued under a SAVEPOINT no longer publish if the root transaction rolls back. Nested rollback also restores pending wakes that were queued before that savepoint.
