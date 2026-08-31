SSH command-line exports copy missing LocalStorage asset objects with one rsync
into the local cache. If rsync is missing locally or on the SSH host, or if it
finishes without caching every requested object, PsyNet warns or stops; there is
no SFTP fallback.
