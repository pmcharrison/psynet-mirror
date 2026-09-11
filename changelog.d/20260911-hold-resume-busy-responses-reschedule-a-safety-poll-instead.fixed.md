A second busy HTTP 503 during hold-resume reschedules the safety poll instead of immediately retrying, so the browser cannot livelock on database contention.
