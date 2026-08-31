Trial candidate discovery no longer lazy-loads ``node.network`` for author
hooks and checks chain growth readiness with the existing SQL predicate instead
of hydrating every trial on the head.
