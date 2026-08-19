Replaced Git and `.dockerignore` deployment file selection with explicit
`deploy.toml` policies as a breaking PsyNet cutover. PsyNet scaffolds
`deploy.toml` (and creates it automatically when missing without overwriting
an existing file). Leftover generated `.dockerignore` files are removed on
debug, deploy, and scaffold; custom copies are preserved with a warning.
Membership no longer depends on Git visibility. This requires Python 3.11
or later and a POSIX filesystem.
