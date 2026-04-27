# PsyNet Patch Release Process

This document describes how to create a patch release (e.g. 13.1.0 → 13.1.1)
from an existing release branch.

## Prerequisites

- You are on the correct release branch (e.g. `release-13.1`).
- All bug-fix commits intended for this release have been cherry-picked or
  committed to the branch.
- The virtual environment is active: `source .venv/bin/activate`
- Dependencies are installed: `uv pip install -e '.[dev,slack]'`

## Steps

### 1. Verify starting state

```bash
git checkout release-13.1
git pull origin release-13.1
git log --oneline v13.1.0..HEAD   # confirm which fixes are included
```

### 2. Bump the version

Update the version string in three files:

| File | Field |
|---|---|
| `.bumpversion.toml` | `current_version` |
| `psynet/version.py` | `psynet_version` |
| `pyproject.toml` | `version` |

Change all occurrences from the old version (e.g. `13.1.0`) to the new version
(e.g. `13.1.1`). Then commit:

```bash
git add .bumpversion.toml psynet/version.py pyproject.toml
git commit -m "Bump version to 13.1.1"
```

### 3. Update demo and test experiments

This updates `requirements.txt`, `constraints.txt`, Dockerfiles, and other
generated files across all demos and tests to reference the new version.

```bash
python3 demos/update_demos.py
```

This can take several minutes because it regenerates `constraints.txt` files.

Then commit:

```bash
git add -A
git commit -m "Update demo and test experiments for PsyNet 13.1.1"
```

### 4. Update the CHANGELOG

Edit `CHANGELOG.md`:

1. Replace the `## Unreleased` header (if present) or insert a new release
   header at the top of the file:

   ```
   # [13.1.1](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.1.1) Release - YYYY-MM-DD
   ```

2. List the changes under appropriate categories (`## Fixed`, `## Changed`,
   `## Added`, `## Updated`, etc.). Each entry should follow the format:

   ```
   - Description of the change (author: Name, reviewer: Name)
   ```

3. Keep the previous release entries below.

Then commit:

```bash
git add CHANGELOG.md
git commit -m "Update CHANGELOG for version 13.1.1"
```

### 5. Tag the release

```bash
git tag v13.1.1
```

### 6. Push branch and tag

```bash
git push origin release-13.1 v13.1.1
```

This triggers the GitLab CI `pages` job which deploys documentation when a
tag matching `^v[0-9]+\.[0-9]+\.[0-9]+$` is pushed.

### 7. Wait for CI to pass

Monitor the GitLab CI pipeline for the pushed tag. The pipeline runs tests
against the tagged commit. **Do not proceed until CI is green.**

Check the pipeline at:
`https://gitlab.com/PsyNetDev/PsyNet/-/pipelines` (filter by tag).

### 8. Build and upload to PyPI

Once CI passes, build the package and upload it to PyPI:

```bash
git checkout v13.1.1
python -m build
twine upload dist/psynet-13.1.1*
```

This builds both the sdist (`.tar.gz`) and wheel (`.whl`) into the `dist/`
directory, then uploads them to PyPI. You will be prompted for PyPI
credentials unless you have a `~/.pypirc` file or a `TWINE_USERNAME` /
`TWINE_PASSWORD` / `TWINE_API_KEY` environment variable configured.

Verify the release is live at https://pypi.org/project/psynet/13.1.1/

Clean up build artifacts afterwards:

```bash
rm -rf dist/ build/ *.egg-info
```

### 9. Create the GitLab release

Go to https://gitlab.com/PsyNetDev/PsyNet/-/releases/new and create a release
from the `v13.1.1` tag, or use the GitLab API / `glab` CLI.

### 10. Merge back to master (if applicable)

If the fix should also appear on master, cherry-pick or merge the release
branch back:

```bash
git checkout master
git merge release-13.1
git push origin master
```

Then bump the master version back to the next alpha if needed
(e.g. `13.2.0a0`).

## Version files reference

The version is tracked in three files, all updated together:

- **`.bumpversion.toml`** — `current_version` field
- **`psynet/version.py`** — `psynet_version` variable
- **`pyproject.toml`** — `version` field under `[project]`

## Naming conventions

- Branch: `release-MAJOR.MINOR` (e.g. `release-13.1`)
- Tag: `vMAJOR.MINOR.PATCH` (e.g. `v13.1.1`)
- Commit messages follow the pattern seen in past releases:
  - `Bump version to X.Y.Z`
  - `Update demo and test experiments for version X.Y.Z`
  - `Update CHANGELOG for version X.Y.Z`
