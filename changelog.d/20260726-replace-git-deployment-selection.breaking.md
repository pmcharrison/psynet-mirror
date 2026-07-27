Replaced Git and `.dockerignore` deployment file selection with explicit
`deploy.toml` policies as a breaking PsyNet cutover. Experiments ship
`deploy.toml`; membership no longer depends on Git visibility or legacy
acknowledgement digests. This deployment prototype requires Python 3.11 or
later and a POSIX filesystem.
