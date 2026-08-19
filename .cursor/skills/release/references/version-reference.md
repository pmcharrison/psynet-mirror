# Version and naming reference


If this release upgrades the Dallinger dependency:

- Update the Dallinger version specifier in `pyproject.toml`
  (e.g. `dallinger[docker]>=12.2.0,<13`).
- Update `recommended_dallinger_major_minor` in `psynet/version.py`.
- Refresh the vendored Dallinger CI constraints snapshot with
  `psynet dev ci update-dallinger-constraints`.

## Version files reference

The version is tracked in two files, both updated together:

- **`psynet/version.py`** — `psynet_version` variable
- **`pyproject.toml`** — `version` field under `[project]`

## Naming conventions

- Release branch: `release-MAJOR.MINOR` (e.g. `release-13.2`)
- Tag: `vMAJOR.MINOR.PATCH` (e.g. `v13.2.0`)
- Post-release bump branch: `bump-master-post-release`
- Commit messages follow the pattern seen in past releases:
  - `Update CHANGELOG for version X.Y.Z`
  - `Bump version to X.Y.Z`
