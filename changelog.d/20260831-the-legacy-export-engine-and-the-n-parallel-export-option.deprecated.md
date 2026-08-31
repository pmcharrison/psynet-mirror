Deprecated `psynet export --legacy`, which downloads the raw database, replaces
the contents of your local database with it, and rebuilds the export locally.
It is retained for one release as a fallback and now prints a warning. The
`--n_parallel` export option is also deprecated: asset export has been
sequential for some time, so the option had no effect.
