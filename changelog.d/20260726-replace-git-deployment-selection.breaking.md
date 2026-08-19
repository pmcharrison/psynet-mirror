Replaced Git and `.dockerignore` deployment file selection with explicit
`deploy.toml` policies as a breaking PsyNet cutover. PsyNet scaffolds
`deploy.toml` (and creates it automatically when missing without overwriting
an existing file). Leftover generated `.dockerignore` files are removed on
debug, deploy, and scaffold; custom copies are preserved with a warning.
The generated experiment `docker/` helper scripts are no longer scaffolded
and are deleted by `psynet scripts update` and on debug/deploy. `psynet setup
--docker` is removed; use `psynet setup` then `psynet debug local --docker`.
Membership no longer depends on Git visibility.
This requires Python 3.11 or later and a POSIX filesystem.
