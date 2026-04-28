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

## Human-in-the-loop policy

Several steps in this process are **externally visible or irreversible**
(e.g. pushing a tag, uploading to PyPI, opening or merging an MR,
publishing a GitLab release). When following this document — and
especially when an AI agent is driving — a human release manager **must
explicitly approve** each of these steps before the corresponding
command is executed.

The mandatory human checkpoints are:

1. **Before pushing the release branch** for the first time (step 5).
2. **Before creating the release MR** on GitLab (step 6).
3. **Before merging the release MR** (step 8) — even after CI is green.
4. **Before pushing the release tag** to `origin` (step 9). Tags
   trigger downstream pipelines and are awkward to revoke.
5. **Before uploading to PyPI** (step 10). PyPI versions can only be
   yanked, never overwritten or deleted; an erroneous upload is
   permanent.
6. **Before creating the GitLab release** (step 11). This is a public
   announcement.
7. **Before merging the post-release `bump-master-post-release` MR**
   (step 12).

The same checkpoints apply at the equivalent points in the
[Release candidates (optional)](#release-candidates-optional) flow:
pushing the release branch, pushing the RC tag, uploading the RC to
PyPI, and creating the GitLab pre-release.

Each step below that requires approval is marked with a
**Human checkpoint** callout. Stop and wait for the release manager's
explicit go-ahead at every such marker; do not chain them.

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

   ```markdown
   # [13.2.0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0) Release - YYYY-MM-DD
   ```

2. Review the entries under appropriate categories (`## Added`, `## Changed`,
   `## Fixed`, `## Removed`, `## Documentation`, etc.). Each entry should
   follow the format:

   ```markdown
   - Description of the change (author: Name, reviewer: Name)
   ```

Then commit:

```bash
git add CHANGELOG.md
git commit -m "Update CHANGELOG for version 13.2.0"
```

### 3. Bump the version

Update the version string in three files:

| File | Field |
| --- | --- |
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

> **Human checkpoint:** confirm with the release manager that the
> three local commits (CHANGELOG, version bump, demo update) look
> correct before the release branch becomes visible on `origin`.

```bash
git push --set-upstream origin release-13.2
```

### 6. Create a merge request

> **Human checkpoint:** the release manager must approve the MR title,
> description, and target branch before it is opened on GitLab.

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

> **Human checkpoint:** even after CI is green, the release manager
> must explicitly approve the merge. This is the point of no return for
> putting the release commits on `master`.

Merge via the GitLab interface using a **merge commit** (not squash).

### 9. Tag the release

> **Human checkpoint:** confirm with the release manager that the merge
> commit on `master` is the intended commit to tag. Pushed tags trigger
> downstream pipelines and are awkward to revoke.

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

> **Human checkpoint:** PyPI uploads are **permanent**. A version can be
> yanked but never overwritten or deleted. The release manager must
> approve both the build and the upload before either command runs.

Once CI passes, build the package and upload it to PyPI:

```bash
git checkout v13.2.0
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/psynet-13.2.0.tar.gz dist/psynet-13.2.0-*.whl
rm -rf dist/ build/ *.egg-info
```

This builds both the sdist (`.tar.gz`) and wheel (`.whl`) into the `dist/`
directory, then uploads them to PyPI. The pre-build `rm -rf` ensures we
start from a clean slate; the upload glob is intentionally narrow because
`dist/psynet-13.2.0*` would also match leftover RC artifacts such as
`psynet-13.2.0rc0*`. The post-upload `rm -rf` removes generated files.

You will be prompted for PyPI credentials unless you have a `~/.pypirc`
file or a `TWINE_USERNAME` / `TWINE_PASSWORD` / `TWINE_API_KEY`
environment variable configured.

Verify the release is live at <https://pypi.org/project/psynet/13.2.0/>.

### 11. Create the GitLab release

> **Human checkpoint:** the GitLab release is the public announcement
> for this version. The release manager must approve the release notes
> before publishing.

#### Release-notes template

Compose a release-notes file (e.g. `release-notes-13.2.0.md`) that
mirrors the corresponding section of `CHANGELOG.md` and points at the
freshly published artifacts. The body should be short — it is meant to
re-state the CHANGELOG, not duplicate it:

```markdown
## What's new in PsyNet 13.2.0

<paste the body of the `# [13.2.0] Release - YYYY-MM-DD` section from
CHANGELOG.md verbatim, keeping the `## Added` / `## Changed` /
`## Fixed` / `## Removed` / `## Documentation` subheadings>

## Links

- PyPI: <https://pypi.org/project/psynet/13.2.0/>
- Documentation: <https://psynetdev.gitlab.io/PsyNet/>
- Full CHANGELOG: <https://gitlab.com/PsyNetDev/PsyNet/-/blob/v13.2.0/CHANGELOG.md>
```

The "Documentation" link points at the docs root because the highest
stable release is always served from there. Once the next minor ships,
the v13.2.0 docs will additionally be archived at
`https://psynetdev.gitlab.io/PsyNet/v13.2.0/` — at which point you can
update older release entries to point at that permanent URL.

#### Option A: GitLab UI

1. Open <https://gitlab.com/PsyNetDev/PsyNet/-/releases/new>.
2. Select the `v13.2.0` tag.
3. Set the release title to `v13.2.0`.
4. Paste the contents of `release-notes-13.2.0.md` into the
   description box.
5. Leave the **pre-release** flag **unticked** (this is a final
   release, not an RC).
6. Click **Create release**.

#### Option B: `glab` CLI

```bash
glab release create v13.2.0 \
  --name "v13.2.0" \
  --notes-file release-notes-13.2.0.md \
  --ref v13.2.0
```

Verify the release is live at
<https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0>.

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

> **Human checkpoint:** the release manager must approve the
> `bump-master-post-release` MR before it is merged.

Merge this MR promptly before any new feature branches land, so the version
on `master` stays aligned with the CHANGELOG.

## Release candidates (optional)

For releases that need wider testing before the final tag, publish one or
more release candidates (RCs) from the release branch first. RCs are
tagged and uploaded to PyPI but are **not** merged back into `master`
until the final release.

Use RCs when:

- The release contains risky or far-reaching changes (e.g. a Dallinger
  upgrade, schema migrations, recruitment-flow changes).
- You want to give experimenters a chance to validate against their own
  studies before the final tag.
- CI is green but you want soak time on real deployments.

### RC0: Cut the first release candidate

Start from the release branch you created in step 1 of the main flow.
Instead of bumping straight to `13.2.0`, bump to `13.2.0rc0` and tag it.

#### 1. Update the CHANGELOG with an RC heading

Edit `CHANGELOG.md`. Rename the `## Unreleased` header to:

```markdown
# [13.2.0rc0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0rc0) Release candidate - YYYY-MM-DD
```

Then add a fresh `## Unreleased` block above it so subsequent fixes have
somewhere to land:

```markdown
## Unreleased

# [13.2.0rc0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0rc0) Release candidate - YYYY-MM-DD

## Added
...
```

Commit:

```bash
git add CHANGELOG.md
git commit -m "Update CHANGELOG for version 13.2.0rc0"
```

#### 2. Bump the version to `13.2.0rc0`

Update `.bumpversion.toml`, `psynet/version.py`, and `pyproject.toml` from
`13.2.0a0` to `13.2.0rc0`. Then commit:

```bash
git add .bumpversion.toml psynet/version.py pyproject.toml
git commit -m "Bump version to 13.2.0rc0"
```

#### 3. Update demo and test experiments

```bash
python3 demos/update_demos.py
git add -A
git commit -m "Update demo and test experiments for PsyNet 13.2.0rc0"
```

#### 4. Push the release branch and tag the RC

> **Human checkpoint:** the release manager must approve before the
> release branch and the RC tag become visible on `origin`. Pushing the
> tag triggers a tag pipeline and the tag is awkward to revoke.

RC tags are pushed directly from the release branch — there is **no MR**
and **no merge to `master`** at this stage.

```bash
git push --set-upstream origin release-13.2
git tag v13.2.0rc0
git push origin v13.2.0rc0
```

Wait for the tag pipeline to pass on GitLab.

#### 5. Build and upload the RC to PyPI

> **Human checkpoint:** PyPI uploads are **permanent**, including for
> release candidates. A version can be yanked but never overwritten or
> deleted. The release manager must approve both the build and the
> upload before either command runs.

```bash
git checkout v13.2.0rc0
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/psynet-13.2.0rc0*
rm -rf dist/ build/ *.egg-info
```

The pre-build `rm -rf` ensures we start from a clean `dist/` so the
upload glob can only match this RC's artifacts.

Verify at <https://pypi.org/project/psynet/13.2.0rc0/>. RCs are not marked
as the latest release on PyPI, so users must opt in with
`pip install psynet==13.2.0rc0`.

#### 6. Create the GitLab pre-release

> **Human checkpoint:** the GitLab pre-release is publicly visible. The
> release manager must approve the pre-release notes before publishing.

##### Release-notes template

Compose a release-notes file (e.g. `release-notes-13.2.0rc0.md`) that
mirrors the RC section of `CHANGELOG.md` and points at the artifacts
specific to this candidate. **Use the `/rc/<tag>/` URL** for docs so
the link is stable across future releases:

```markdown
## What's new in PsyNet 13.2.0rc0

<paste the body of the `# [13.2.0rc0] Release candidate - YYYY-MM-DD`
section from CHANGELOG.md verbatim, keeping the `## Added` /
`## Changed` / `## Fixed` / `## Removed` / `## Documentation`
subheadings>

This is a **release candidate**. It is not the latest release on PyPI;
opt in explicitly with `pip install psynet==13.2.0rc0`. Please test
against your studies and report any regressions before the final
13.2.0 tag.

## Links

- PyPI: <https://pypi.org/project/psynet/13.2.0rc0/>
- RC documentation: <https://psynetdev.gitlab.io/PsyNet/rc/v13.2.0rc0/>
- Full CHANGELOG: <https://gitlab.com/PsyNetDev/PsyNet/-/blob/v13.2.0rc0/CHANGELOG.md>
```

##### Option A: GitLab UI

1. Open <https://gitlab.com/PsyNetDev/PsyNet/-/releases/new>.
2. Select the `v13.2.0rc0` tag.
3. Set the release title to `v13.2.0rc0 (Release candidate)`.
4. Paste the contents of `release-notes-13.2.0rc0.md` into the
   description box.
5. **Tick the pre-release flag.** This is critical — it prevents the
   RC from showing up as the project's "latest release" and signals to
   users that the artifact is for testing only.
6. Click **Create release**.

##### Option B: `glab` CLI

```bash
glab release create v13.2.0rc0 \
  --name "v13.2.0rc0 (Release candidate)" \
  --notes-file release-notes-13.2.0rc0.md \
  --ref v13.2.0rc0
```

`glab release create` does not currently expose a flag for the
pre-release checkbox. After running the command, open
<https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0rc0/edit> and
**tick the pre-release flag manually**. Then announce the RC to the
team and users you want feedback from.

### Iterate: RC1, RC2, …

While the RC is being tested, additional fixes may need to land on the
release branch. Prefer to land the fix on `master` first via a normal MR,
then cherry-pick it onto the release branch:

```bash
git checkout master
git pull origin master
# fix lands on master via a normal MR (or directly if appropriate)

git checkout release-13.2
git pull origin release-13.2
git cherry-pick <commit-sha>
git push origin release-13.2
```

If a fix only makes sense on the release branch (e.g. a release-only
revert), commit it directly on `release-13.2` and remember to port it
back to `master` later if needed.

When you have enough fixes to justify another candidate, cut the next
RC by repeating the same four-commit sequence with the next RC number
(e.g. `13.2.0rc1`):

1. Add a new `# [13.2.0rc1](...) Release candidate - YYYY-MM-DD` heading
   to `CHANGELOG.md` describing only the changes since the previous RC.
   Move entries between RC sections if a fix that was logged under the
   previous RC was actually only completed in this one.

   ```bash
   git add CHANGELOG.md
   git commit -m "Update CHANGELOG for version 13.2.0rc1"
   ```

2. Bump version to `13.2.0rc1` in the three version files.

   ```bash
   git add .bumpversion.toml psynet/version.py pyproject.toml
   git commit -m "Bump version to 13.2.0rc1"
   ```

3. Run `python3 demos/update_demos.py`.

   ```bash
   git add -A
   git commit -m "Update demo and test experiments for PsyNet 13.2.0rc1"
   ```

4. Push the branch, tag `v13.2.0rc1`, push the tag, build and upload to
   PyPI, and create the GitLab pre-release as before.

   > **Human checkpoint:** apply the same approvals as for RC0 — push
   > of branch and tag, PyPI upload, and GitLab pre-release each
   > require explicit release-manager approval.

Repeat for `rc2`, `rc3`, etc. until you are confident the release is
ready.

### Promote the final RC to the official release

Once the latest RC has been validated and no further changes are needed:

1. Consolidate the RC headings in `CHANGELOG.md` into a single
   `# [13.2.0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0) Release - YYYY-MM-DD`
   section by:
   - Replacing the most recent RC heading with the final release heading
     and dating it.
   - Merging entries from earlier RC sections into the appropriate
     `## Added` / `## Changed` / `## Fixed` / `## Removed` /
     `## Documentation` subsections of the final release.
   - Removing the now-empty intermediate RC headings.

2. Bump the version from `13.2.0rcN` to `13.2.0` in `.bumpversion.toml`,
   `psynet/version.py`, and `pyproject.toml`.

3. Run `python3 demos/update_demos.py`.

4. Commit each step using the standard messages
   (`Update CHANGELOG for version 13.2.0`, `Bump version to 13.2.0`,
   `Update demo and test experiments for PsyNet 13.2.0`).

5. Resume the main release flow from
   [step 6 (Create a merge request)](#6-create-a-merge-request) onwards
   to merge the release branch into `master`, tag `v13.2.0`, and publish
   to PyPI.

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
