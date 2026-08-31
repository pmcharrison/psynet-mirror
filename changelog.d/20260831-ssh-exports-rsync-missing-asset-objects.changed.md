SSH command-line exports copy missing local-storage asset objects with one rsync
into a persistent content-addressed cache, so repeat exports transfer only new
objects. If rsync is unavailable locally or on the SSH host, the export falls
back to a complete server-built archive. If rsync finishes without caching every
requested object, the export stops rather than publishing an incomplete result.
