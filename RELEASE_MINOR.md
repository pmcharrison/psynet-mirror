# PsyNet Minor Release Process

This document describes how to create a minor release (e.g. 13.1.0 → 13.2.0)
from the `master` branch. Minor releases include new features and bugfixes
that are backwards-compatible.

For patch releases on an existing release branch, see `RELEASE_PATCH.md`.

## Prerequisites

- All merge requests intended for this release have been merged into `master`.
- `master` CI is green.
- The virtual environment is active: `source .venv/bin/activate`
- Dependencies are installed: `uv pip install -e '.[dev,slack]'`

## Steps

### 1. Create the release branch

Create a new release branch from `master`. The branch name uses
`MAJOR.MINOR` (without the patch number):

```bash
git checkout master
git pull origin master
git checkout -b release-13.2
```

### 2. Update the CHANGELOG

Edit `CHANGELOG.md`:

1. Rename the `## Unreleased` header to a release header:

   ```
   # [13.2.0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0) Release - YYYY-MM-DD
   ```

2. Review the entries under appropriate categories (`## Added`, `## Changed`,
   `## Fixed`, `## Removed`, `## Documentation`, etc.). Each entry should
   follow the format:

   ```
   - Description of the change (author: Name, reviewer: Name)
   ```

3. Cross-check against merged MRs since the last release tag to make sure
   nothing is missing:

   ```bash
   git log --oneline v13.1.0..HEAD --merges
   ```

4. Close associated GitLab issues with a comment linking them to the MR:
   "Implemented in !ABC".

Then commit:

```bash
git add CHANGELOG.md
git commit -m "Update CHANGELOG for version 13.2.0"
```

### 3. Bump the version

Update the version string in three files:

| File | Field |
|---|---|
| `.bumpversion.toml` | `current_version` |
| `psynet/version.py` | `psynet_version` |
| `pyproject.toml` | `version` |

Change all occurrences from the alpha version (e.g. `13.2.0a0`) to the
release version (e.g. `13.2.0`). Then commit:

```bash
git add .bumpversion.toml psynet/version.py pyproject.toml
git commit -m "Bump version to 13.2.0"
```

### 4. Update demo and test experiments

This updates `requirements.txt`, `constraints.txt`, Dockerfiles, and other
generated files across all demos and tests to reference the new version.

```bash
python3 demos/update_demos.py
```

This can take several minutes because it regenerates `constraints.txt` files.

Then commit:

```bash
git add -A
git commit -m "Update demo and test experiments for PsyNet 13.2.0"
```

### 5. Push the release branch

```bash
git push --set-upstream origin release-13.2
```

### 6. Create a merge request

Create an MR on GitLab to merge the release branch into `master`:

- **Title:** `Release version 13.2.0`
- Review the changes one last time in the MR "Changes" tab.
- Use a **merge commit** (do not squash), so the individual release commits
  are preserved on `master`.

### 7. Wait for CI to pass

Monitor the GitLab CI pipeline for the MR. **Do not proceed until CI is
green.**

Check the pipeline at:
`https://gitlab.com/PsyNetDev/PsyNet/-/pipelines`

### 8. Merge the MR

Merge via the GitLab interface using a **merge commit** (not squash).

### 9. Tag the release

After merging, tag the merge commit on `master`:

```bash
git checkout master
git pull origin master
git tag v13.2.0
git push origin v13.2.0
```

Pushing the tag triggers the CI test pipeline for the tagged commit.
Documentation is deployed separately via the `pages_latest` CI job when
changes land on the default branch.

### 10. Build and upload to PyPI

Once CI passes, build the package and upload it to PyPI:

```bash
git checkout v13.2.0
python -m build
twine upload dist/psynet-13.2.0*
```

This builds both the sdist (`.tar.gz`) and wheel (`.whl`) into the `dist/`
directory, then uploads them to PyPI. You will be prompted for PyPI
credentials unless you have a `~/.pypirc` file or a `TWINE_USERNAME` /
`TWINE_PASSWORD` / `TWINE_API_KEY` environment variable configured.

Verify the release is live at https://pypi.org/project/psynet/13.2.0/

Clean up build artifacts afterwards:

```bash
rm -rf dist/ build/ *.egg-info
```

### 11. Create the GitLab release

Go to https://gitlab.com/PsyNetDev/PsyNet/-/releases/new and create a release
from the `v13.2.0` tag, or use the GitLab API / `glab` CLI.

### 12. Bump master to the next alpha

After the release is published, bump `master` to the next development version:

```bash
git checkout master
git pull origin master
git checkout -b bump-master-post-release
```

Update the version in three files from `13.2.0` to `13.3.0a0`, and add back
the `## Unreleased` header at the top of `CHANGELOG.md`:

```markdown
## Unreleased
```

Then commit and open a MR:

```bash
git add .bumpversion.toml psynet/version.py pyproject.toml CHANGELOG.md
git commit -m "Bump version to 13.3.0a0"
git push --set-upstream origin bump-master-post-release
```

Merge this MR promptly before any new feature branches land, so the version
on `master` stays aligned with the CHANGELOG.

## Release candidates (optional)

For releases that need wider testing before the final tag, use release
candidates. These follow the same steps above but with RC version strings:

1. Bump to `13.2.0rc0` (then `rc1`, `rc2`, etc.) instead of `13.2.0`.
2. Tag as `v13.2.0rc0`.
3. Publish to PyPI as usual.
4. Collect feedback and cherry-pick fixes onto the release branch.
5. When ready, bump to `13.2.0` and proceed with the final release.

## Dallinger version considerations

If this release upgrades the Dallinger dependency:

- Update the Dallinger version specifier in `pyproject.toml`
  (e.g. `dallinger[docker]>=12.2.0,<13`).
- Update `recommended_dallinger_major_minor` in `psynet/version.py`.
- Make sure the correct Dallinger version is installed in your environment
  before running `demos/update_demos.py`, as the script uses it to resolve
  constraint versions.

## Version files reference

The version is tracked in three files, all updated together:

- **`.bumpversion.toml`** — `current_version` field
- **`psynet/version.py`** — `psynet_version` variable
- **`pyproject.toml`** — `version` field under `[project]`

## Naming conventions

- Release branch: `release-MAJOR.MINOR` (e.g. `release-13.2`)
- Tag: `vMAJOR.MINOR.PATCH` (e.g. `v13.2.0`)
- Post-release bump branch: `bump-master-post-release`
- Commit messages follow the pattern seen in past releases:
  - `Update CHANGELOG for version X.Y.Z`
  - `Bump version to X.Y.Z`
  - `Update demo and test experiments for PsyNet X.Y.Z`
