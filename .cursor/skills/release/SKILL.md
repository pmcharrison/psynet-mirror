---
name: release
description: Guide a PsyNet release (minor from master, or patch from an existing release branch), including changelog, version bump, demo updates, tagging, PyPI upload, GitLab release, Slack announcement, release candidates, and human checkpoints.
---

# PsyNet Release Process

Invoke this skill in Cursor with the release type as an argument, e.g.
`/release minor` or `/release patch`. If no release type is given, ask the
user which one applies before proceeding.

This skill covers both release types:

- **Minor release** (e.g. 13.1.0 → 13.2.0): cut from `master`; new
  backwards-compatible features and bugfixes. Follow
  [Minor release path](#minor-release-path).
- **Patch release** (e.g. 13.1.0 → 13.1.1): cut from an existing
  `release-MAJOR.MINOR` branch; bug fixes only. Follow
  [Patch release path](#patch-release-path).

Both paths use the same [shared steps](#shared-steps) for the changelog,
version bump, demo updates, tagging, PyPI upload, GitLab release, and Slack
announcement. Throughout, `X.Y.Z` stands for the version being released.

## Prerequisites

- The virtual environment is active: `source .venv/bin/activate`
- Dependencies are installed: `uv pip install -e '.[dev,slack]'`
- For a **minor** release: all merge requests intended for the release have
  been merged into `master`, and `master` CI is green.
- For a **patch** release: all bug-fix commits intended for the release have
  been cherry-picked or committed to the release branch.

### Pre-existing local changes

Ignore all unstaged and untracked files that already exist in the working
tree when the release starts (e.g. local scratch files, in-progress work
from other branches, uncommitted changelog fragments). They must not be
committed as part of any release commit. This is why the steps below stage
explicit paths and never use `git add -A` or `git add .`: only files
generated or edited by the release steps themselves belong in the release
commits. In particular, keep untracked `changelog.d/` fragments belonging
to unmerged work out of the folded CHANGELOG (move them aside before
running `psynet dev changelog release`, and restore them afterwards).

## Human-in-the-loop policy

Several steps in this process are **externally visible or irreversible**
(e.g. pushing a branch or tag, uploading to PyPI, opening or merging an MR,
publishing a GitLab release, posting to Slack). When following this skill —
and especially when an AI agent is driving — a human release manager **must
explicitly approve** each of these steps before the corresponding command is
executed. This policy applies to minor releases, patch releases, and release
candidates alike.

The mandatory human checkpoints are:

1. **Before pushing a release branch** (new or updated) to `origin`.
2. **Before creating or merging an MR** on GitLab.
3. **Before pushing a release tag** to `origin`. Tags trigger downstream
   pipelines and are awkward to revoke.
4. **Before uploading to PyPI.** PyPI versions can only be yanked, never
   overwritten or deleted; an erroneous upload is permanent.
5. **Before creating the GitLab release.** This is a public announcement.
6. **Before posting the Slack announcement** to `#psynet-support`. The
   message is broadcast and cannot be unsent (only edited or deleted).

Each step below that requires approval is marked with a
**Human checkpoint** callout. Stop and wait for the release manager's
explicit go-ahead at every such marker; do not chain them.

## Shared steps

These steps are referenced from both release paths (and the RC flow). Perform
them in the order given by the path you are following.

### Update the CHANGELOG

Generate the release section from committed changelog fragments:

```bash
psynet dev changelog release X.Y.Z YYYY-MM-DD
```

This folds all fragments in `changelog.d/` into a
`# [X.Y.Z](https://gitlab.com/PsyNetDev/PsyNet/-/releases/vX.Y.Z) Release - YYYY-MM-DD`
section in `CHANGELOG.md` and removes the consumed fragments. Future changes
should add new fragment files with `psynet dev changelog new`.

Review the generated section under the appropriate categories (`## Added`,
`## Changed`, `## Fixed`, `## Removed`, `## Documentation`, etc.). Each entry
should be a user-facing sentence, without author/reviewer metadata, and should
end with a period.

Then commit. Note that `git add changelog.d` stages untracked fragments
too, so make sure any fragments belonging to unmerged work have been moved
aside first (see [Pre-existing local changes](#pre-existing-local-changes)):

```bash
git add CHANGELOG.md changelog.d
git commit -m "Update CHANGELOG for version X.Y.Z"
```

### Bump the version

Update the version string in two files:

| File | Field |
| --- | --- |
| `psynet/version.py` | `psynet_version` |
| `pyproject.toml` | `version` |

Change all occurrences from the old version to the new version. Then commit:

```bash
git add psynet/version.py pyproject.toml
git commit -m "Bump version to X.Y.Z"
```

### Update demo and test experiments

This updates `requirements.txt`, `constraints.txt`, Dockerfiles, and other
generated files across all demos and tests to reference the new version.

```bash
psynet dev experiments update
```

This can take several minutes because it regenerates `constraints.txt` files.

Then commit. Stage explicit paths rather than `git add -A`, so unrelated
untracked files in the working tree are not swept into the release commit.
The command touches three locations — do not forget the experiment-script
templates under `psynet/resources/`, which include the Docker image tag in
`psynet/resources/experiment_scripts/docker/generate-constraints`:

```bash
git add demos tests psynet/resources
git commit -m "Update demo and test experiments for PsyNet X.Y.Z"
```

Afterwards run `git status` and confirm no tracked files remain modified;
if any do, they were generated by the update and belong in this commit.

### Tag the release

> **Human checkpoint:** confirm with the release manager that the current
> release-branch commit is the intended commit to tag. Pushed tags trigger
> downstream pipelines and are awkward to revoke.

Tag the release branch commit, not `master`. This ensures the release
contains exactly the commits prepared on the release branch, even if
`master` has moved since the branch was created.

```bash
git checkout release-X.Y
git pull origin release-X.Y
git tag vX.Y.Z
git push origin vX.Y.Z
```

Pushing the tag triggers the CI test pipeline for the tagged commit. The
tag pipeline also includes the `pages` job, which builds and deploys the
documentation for the tag (see
[Verify the documentation deployment](#verify-the-documentation-deployment)).

### Wait for CI to pass

Monitor the GitLab CI pipeline for the release branch/MR/tag. **Do not
proceed until CI is green.**

Check the pipeline at:
`https://gitlab.com/PsyNetDev/PsyNet/-/pipelines`

### Verify the documentation deployment

The `pages` job in the tag pipeline builds the documentation for the
tagged version and publishes it to GitLab Pages:

- **Stable tags** (`vX.Y.Z`) are published to
  `https://psynetdev.gitlab.io/PsyNet/vX.Y.Z/`, and additionally to the
  docs root when the tag is the highest stable release.
- **Prerelease tags** (`vX.Y.ZrcN`, `vX.Y.ZaN`) are published to
  `https://psynetdev.gitlab.io/PsyNet/rc/vX.Y.ZrcN/`.

After the `pages` job has finished (Pages deployment can take a few extra
minutes after the job succeeds), verify:

1. The tag's docs URL above loads and shows the correct version number in
   the page header.
2. The new version is accessible from the version dropdown menu at
   <https://psynetdev.gitlab.io/PsyNet/>. The dropdown is driven by
   `https://psynetdev.gitlab.io/PsyNet/_static/version_switcher.json`, so
   you can also check programmatically that the JSON contains an entry
   for the tag:

   ```bash
   curl -s https://psynetdev.gitlab.io/PsyNet/_static/version_switcher.json | python3 -m json.tool
   ```

If the tag is missing from the dropdown or its docs URL 404s, inspect the
`pages` job log in the tag pipeline before proceeding to the announcement
steps.

### Build and upload to PyPI

> **Human checkpoint:** PyPI uploads are **permanent**. A version can be
> yanked but never overwritten or deleted. The release manager must
> approve both the build and the upload before either command runs.

Once CI passes, build the package and upload it to PyPI:

```bash
git checkout vX.Y.Z
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/psynet-X.Y.Z.tar.gz dist/psynet-X.Y.Z-*.whl
rm -rf dist/ build/ *.egg-info
```

This builds both the sdist (`.tar.gz`) and wheel (`.whl`) into the `dist/`
directory, then uploads them to PyPI. The pre-build `rm -rf` ensures we
start from a clean slate; the upload glob is intentionally narrow because
`dist/psynet-X.Y.Z*` would also match leftover RC artifacts such as
`psynet-X.Y.Zrc1*`. The post-upload `rm -rf` removes generated files.

You will be prompted for PyPI credentials unless you have a `~/.pypirc`
file or a `TWINE_USERNAME` / `TWINE_PASSWORD` / `TWINE_API_KEY`
environment variable configured.

Verify the release is live at `https://pypi.org/project/psynet/X.Y.Z/`.

### Create the GitLab release

> **Human checkpoint:** the GitLab release is the public announcement
> for this version. The release manager must approve the release notes
> before publishing.

This step applies to **final releases only**. Release candidates and
other prereleases are tag-only on GitLab — see
[Release candidates](#release-candidates-minor-releases) for why.

Compose a release-notes file (e.g. `release-notes-X.Y.Z.md`) that
mirrors the corresponding section of `CHANGELOG.md` and points at the
freshly published artifacts. The body should be short — it is meant to
re-state the CHANGELOG, not duplicate it:

```markdown
## What's new in PsyNet X.Y.Z

<paste the body of the `# [X.Y.Z] Release - YYYY-MM-DD` section from
CHANGELOG.md verbatim, keeping the `## Added` / `## Changed` /
`## Fixed` / `## Removed` / `## Documentation` subheadings>

## Links

- PyPI: <https://pypi.org/project/psynet/X.Y.Z/>
- Documentation: <https://psynetdev.gitlab.io/PsyNet/>
- Full CHANGELOG: <https://gitlab.com/PsyNetDev/PsyNet/-/blob/vX.Y.Z/CHANGELOG.md>
```

The "Documentation" link points at the docs root because the highest
stable release is always served from there. Once the next release ships,
the vX.Y.Z docs will additionally be archived at
`https://psynetdev.gitlab.io/PsyNet/vX.Y.Z/` — at which point you can
update older release entries to point at that permanent URL.

#### Option A: GitLab UI

1. Open <https://gitlab.com/PsyNetDev/PsyNet/-/releases/new>.
2. Select the `vX.Y.Z` tag.
3. Set the release title to `X.Y.Z` (the version number without the
   tag's `v` prefix).
4. Paste the contents of `release-notes-X.Y.Z.md` into the
   description box.
5. Leave the **pre-release** flag **unticked** for final releases.
   (Tick it only for release candidates; see the RC flow.)
6. Click **Create release**.

#### Option B: `glab` CLI

```bash
glab release create vX.Y.Z \
  --name "X.Y.Z" \
  --notes-file release-notes-X.Y.Z.md \
  --ref vX.Y.Z
```

Verify the release is live at
`https://gitlab.com/PsyNetDev/PsyNet/-/releases/vX.Y.Z`.

### Announce the release on Slack

> **Human checkpoint:** the Slack post is broadcast to
> `#psynet-support` and cannot be unsent. The release manager must
> approve the message body before posting.

Use the `psynet dev release announce` command. It composes the message
envelope (title, RC notice, upgrade instructions, links) from the
version argument and posts using the `[slack]` extra (already installed
via the prerequisites). Set `SLACK_BOT_TOKEN` to a bot token that has
`chat:write` access to the channel. If the token is not set in the
environment and not present in the user's `~/.zshrc` or `~/.bashrc`
(check for the variable name only; never print the value), ask the user
to paste the token.

**Write the experimenter-facing summary yourself.** The command does
not generate the changes summary; you supply it via `--summary-file`.
Read the release's section in `CHANGELOG.md` (for tagged versions:
`git show vX.Y.Z:CHANGELOG.md`) and write a Slack-mrkdwn highlights
file, e.g. `/tmp/release-highlights-X.Y.Z.md`:

- Use `*Category*` headers in this order, keeping only non-empty ones:
  Breaking, Added, Changed, Deprecated, Removed, Fixed.
- One `•` bullet per entry, condensed to its essential point (drop
  leading "Added"/"Fixed", trailing rationale clauses, and author
  metadata). Use single `*` for bold and single backticks for code.
- **Include** what affects people building or running experiments:
  experiment API changes (timeline, trials, trial makers, assets,
  sync groups, modular pages), recruiter changes (Prolific/Lucid),
  anything under Breaking/Deprecated/Removed, deploy/export/debug
  command changes, translation and demo changes.
- **Exclude** maintainer-facing items: CI, tests, benchmarks, docs
  scripts, release tooling (`psynet dev` commands), Cursor skills, and
  internal refactors with no observable behavior change.
- **Add references to high-value bullets** using inline Slack links
  (`<URL|label>`):
  - Link major new features and Breaking/Deprecated/Removed items to
    the relevant documentation section. For release candidates, use
    the RC docs site (`https://psynetdev.gitlab.io/PsyNet/rc/vX.Y.ZrcN/...`)
    so links show the new behavior.
  - Link mentioned classes/APIs to their API reference anchor when one
    exists (e.g. `api/sync.html#psynet.sync.SyncGroup`); check the
    defining module against `docs/api/` and confirm the anchor is
    present on the rendered page before linking.
  - Link new or moved demos to their directory in the repo at the tag
    (`https://gitlab.com/PsyNetDev/PsyNet/-/tree/vX.Y.Z/demos/...`),
    and also to the demo's docs page when one exists (check
    `docs/demos/` for a matching `.rst`).
  - Link to external sources when a change is driven by a third-party
    platform — e.g. a Prolific or Lucid announcement or documentation
    page explaining an API change that motivated a removal or new
    behavior.
  - Do not link every bullet — small fixes need no reference.
  - **Verify each URL resolves** (e.g. `curl -sI -o /dev/null
    -w '%{http_code}' <url>`) before posting; a 404 in an announcement
    is worse than no link.

Then preview and post:

```bash
psynet dev release announce X.Y.Z --summary-file /tmp/release-highlights-X.Y.Z.md --dry-run
psynet dev release announce X.Y.Z --summary-file /tmp/release-highlights-X.Y.Z.md --channel testing-bot-messages
psynet dev release announce X.Y.Z --summary-file /tmp/release-highlights-X.Y.Z.md
```

The dry run prints the exact body that would be posted; have the
release manager check the summary against the CHANGELOG section for
missing or superfluous bullets. Then post to the
`#testing-bot-messages` channel, so the release manager can review the
actual Slack rendering (link previews, mrkdwn formatting, block layout)
before the real announcement; only after that review post to
`#psynet-support`. The message uses Slack `mrkdwn` syntax (single `*`
for bold, `<URL|label>` for inline links); the final-release template
looks like:

```text
*:tada: PsyNet X.Y.Z is out*

• <https://gitlab.com/PsyNetDev/PsyNet/-/releases/vX.Y.Z|Release notes>
• <https://pypi.org/project/psynet/X.Y.Z/|PyPI>
• <https://psynetdev.gitlab.io/PsyNet/|Documentation>

Upgrade with `pip install --upgrade psynet`.
```

If you would rather post manually, copy the dry-run output verbatim
into a message in `#psynet-support`.

## Minor release path

Example: releasing 13.2.0 from `master` while `master` is at `13.2.0a0`.

**Default to a release candidate first.** For minor releases, cut an RC
(e.g. `13.2.0rc1`) before the final version, unless the release manager
explicitly instructs otherwise. After creating the release branch (step 1
below), switch to the [release candidate flow](#release-candidates-minor-releases)
instead of continuing with steps 2–7; return to the final-release steps via
[Promote the final RC to the official release](#promote-the-final-rc-to-the-official-release)
once the RC has been validated.

### 1. Create the release branch

Create a new release branch from `master`. The branch name uses
`MAJOR.MINOR` (without the patch number):

```bash
git checkout master
git pull origin master
git checkout -b release-13.2
```

### 2. Prepare the release commits

Perform the shared steps, in this order:

1. [Update the CHANGELOG](#update-the-changelog)
2. [Bump the version](#bump-the-version) (from the alpha version, e.g.
   `13.2.0a0` → `13.2.0`)
3. [Update demo and test experiments](#update-demo-and-test-experiments)

### 3. Push the release branch

> **Human checkpoint:** confirm with the release manager that the
> three local commits (CHANGELOG, version bump, demo update) look
> correct before the release branch becomes visible on `origin`.

```bash
git push --set-upstream origin release-13.2
```

### 4. Create a merge request

> **Human checkpoint:** the release manager must approve the MR title,
> description, and target branch before it is opened on GitLab.

Create an MR on GitLab to merge the release branch into `master`, but
**do not merge it yet**. The final release tag must be created from the
release branch, not from a later merge commit on `master`, because `master`
may have gained additional changes after the release branch was created.

- **Title:** `Release version 13.2.0`
- **Label:** apply the `Release` label, either at creation
  (`glab mr create ... --label Release`) or afterwards
  (`glab mr update <iid> --label Release`).
- Review the changes one last time in the MR "Changes" tab.
- Use a **merge commit** (do not squash), so the individual release commits
  are preserved on `master`.
- Disable source-branch deletion. Release branches are long-lived maintenance
  branches and must remain available after they are merged back into `master`.

### 5. Publish

Perform the shared steps, in this order:

1. [Wait for CI to pass](#wait-for-ci-to-pass)
2. [Tag the release](#tag-the-release)
3. [Build and upload to PyPI](#build-and-upload-to-pypi)
4. [Verify the documentation deployment](#verify-the-documentation-deployment)
5. [Create the GitLab release](#create-the-gitlab-release)
6. [Announce the release on Slack](#announce-the-release-on-slack)

### 6. Merge the release branch back into master

> **Human checkpoint:** even after the release has been tagged and
> published, the release manager must explicitly approve merging the
> release branch back into `master`.

Merge the release MR via the GitLab interface using a **merge commit** (not
squash), and make sure the source branch is not deleted. This carries forward
release bookkeeping such as the finalized `CHANGELOG.md`, version bump, and
regenerated demo constraints. It is not the commit that should be tagged for
the release.

### 7. Bump master to the next alpha

After the release branch has been merged back into `master`, bump `master`
to the next development version:

```bash
git checkout master
git pull origin master
git checkout -b bump-master-post-release
```

Update the version in both version files from `13.2.0` to `13.3.0a0`.
Then regenerate demo and test experiment files so `master` demos track the
current alpha version:

```bash
psynet dev experiments update
```

New changes on `master` should be recorded as fragments in `changelog.d/`.

Then commit the version bump and generated demo/test updates, and open a MR:

```bash
git add -A
git commit -m "Bump version to 13.3.0a0"
git push --set-upstream origin bump-master-post-release
```

> **Human checkpoint:** the release manager must approve the
> `bump-master-post-release` MR before it is merged.

Merge this MR promptly before any new feature branches land, so the version
and generated demo/test files on `master` stay aligned with the CHANGELOG.

## Patch release path

Example: releasing 13.1.1 from the existing `release-13.1` branch.

### 1. Verify starting state

```bash
git checkout release-13.1
git pull origin release-13.1
git log --oneline v13.1.0..HEAD   # confirm which fixes are included
```

### 2. Prepare the release commits

Perform the shared steps, in this order:

1. [Update the CHANGELOG](#update-the-changelog) — cherry-picked fixes
   carry their `changelog.d/` fragments with them; fold them into the
   patch release section. Add fragments manually for any fix that is
   missing one.
2. [Bump the version](#bump-the-version) (e.g. `13.1.0` → `13.1.1`)
3. [Update demo and test experiments](#update-demo-and-test-experiments)

### 3. Push the release branch

> **Human checkpoint:** confirm with the release manager that the local
> commits look correct before they become visible on `origin`.

```bash
git push origin release-13.1
```

### 4. Publish

Perform the shared steps, in this order:

1. [Tag the release](#tag-the-release)
2. [Wait for CI to pass](#wait-for-ci-to-pass) (the tag pipeline runs
   tests against the tagged commit)
3. [Build and upload to PyPI](#build-and-upload-to-pypi)
4. [Verify the documentation deployment](#verify-the-documentation-deployment)
5. [Create the GitLab release](#create-the-gitlab-release)
6. [Announce the release on Slack](#announce-the-release-on-slack)

### 5. Merge back to master (if applicable)

> **Human checkpoint:** the release manager must approve merging or
> cherry-picking release-branch fixes back into `master`.

If the fix should also appear on `master`, cherry-pick or merge the release
branch back:

```bash
git checkout master
git merge release-13.1
git push origin master
```

`master` should remain on its current alpha version (e.g. `13.2.0a0`);
restore it if the merge changed the version files.

## Release candidates (minor releases)

Publishing one or more release candidates (RCs) from the release branch
before the final tag is the **default** for minor releases; skip straight
to the final version only when the release manager explicitly instructs
otherwise. RCs are tagged and uploaded to PyPI but are **not** merged back
into `master` until the final release.

The human checkpoints from the
[Human-in-the-loop policy](#human-in-the-loop-policy) apply at the
equivalent points: pushing the release branch, pushing the RC tag,
uploading the RC to PyPI, and posting the Slack announcement.

RCs are **tag-only** on GitLab: do **not** create a GitLab release entry
for them. GitLab has no pre-release flag (unlike GitHub), so an RC
release entry would become the project's "latest release" (permalink,
releases feed, and badge) until the final version ships. This tag-only
convention matches what major GitLab-hosted projects (GitLab Runner,
Inkscape, Wireshark) do. The RC's changelog section, PyPI page, and docs
build carry all the information testers need.

Number release candidates starting from **rc1** (`13.2.0rc1`, `13.2.0rc2`,
…), matching the common convention across major projects. (Releases up to
13.3.0 started at `rc0`.)

RCs are especially valuable when:

- The release contains risky or far-reaching changes (e.g. a Dallinger
  upgrade, schema migrations, recruitment-flow changes).
- You want to give experimenters a chance to validate against their own
  studies before the final tag.
- CI is green but you want soak time on real deployments.

### RC1: Cut the first release candidate

Start from the release branch created in step 1 of the minor release path.
Instead of bumping straight to `13.2.0`, bump to `13.2.0rc1` and tag it,
using the shared steps with the RC version:

1. [Update the CHANGELOG](#update-the-changelog) with
   `psynet dev changelog release 13.2.0rc1 YYYY-MM-DD`. This creates a
   `# [13.2.0rc1](...) Release candidate - YYYY-MM-DD` section. If further
   changes land before the next RC or final release, record them as new
   fragments in `changelog.d/`.
2. [Bump the version](#bump-the-version) from `13.2.0a0` to `13.2.0rc1`.
3. [Update demo and test experiments](#update-demo-and-test-experiments).
4. Push the release branch and tag the RC. RC tags are pushed directly from
   the release branch — there is **no MR** and **no merge to `master`** at
   this stage:

   ```bash
   git push --set-upstream origin release-13.2
   git tag v13.2.0rc1
   git push origin v13.2.0rc1
   ```

   Wait for the tag pipeline to pass on GitLab.
5. [Build and upload to PyPI](#build-and-upload-to-pypi) using the RC
   version. Since the pre-build `rm -rf` guarantees a clean `dist/`, the
   broader glob `dist/psynet-13.2.0rc1*` is safe here. RCs are not marked
   as the latest release on PyPI, so users must opt in with
   `pip install psynet==13.2.0rc1`.
6. [Verify the documentation deployment](#verify-the-documentation-deployment):
   confirm that `https://psynetdev.gitlab.io/PsyNet/rc/v13.2.0rc1/` loads
   and that the RC appears in the version dropdown at
   <https://psynetdev.gitlab.io/PsyNet/>.
7. **Skip the GitLab release entry.** RCs are tag-only on GitLab (see
   above); the [Create the GitLab release](#create-the-gitlab-release)
   step applies to final releases only.
8. [Announce the release on Slack](#announce-the-release-on-slack) with the
   RC version, writing the highlights file from the RC's CHANGELOG
   section as described there. `psynet dev release announce 13.2.0rc1
   --summary-file ...` auto-detects the `rc` segment and generates an
   RC-flavoured envelope with the `/rc/<tag>/` docs URL, the
   CHANGELOG-at-tag link (since there is no GitLab release entry), and
   the opt-in install instruction:

   ```text
   *:test_tube: PsyNet 13.2.0rc1 (release candidate) is out*

   • <https://gitlab.com/PsyNetDev/PsyNet/-/blob/v13.2.0rc1/CHANGELOG.md|Release notes>
   • <https://pypi.org/project/psynet/13.2.0rc1/|PyPI>
   • <https://psynetdev.gitlab.io/PsyNet/rc/v13.2.0rc1/|Documentation>

   Opt in with `pip install psynet==13.2.0rc1`. Please test against your
   studies and report any regressions before the final tag.
   ```

   Tag any specific people whose feedback you need on a thread under the
   post rather than `@channel`-ing the whole channel.
9. **Validate the RC with a deployment test.** Run the deployment test
   suite against the RC tag by following the `deployment-test` skill
   (`.cursor/skills/deployment-test/SKILL.md`): by default this deploys
   the two Prolific test experiments (`payment_flows_prolific` and
   `audio_gibbs`) in parallel plus the `audio_gibbs` Lucid variant. The
   skill's default flow — basing the deployment branch on the latest
   release tag, including RCs — is designed for exactly this step. The
   test produces a committed `analysis.md` per app on the deployment
   branch; their verdicts feed the promotion decision below.

### Iterate: RC2, RC3, …

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

When you have enough fixes to justify another candidate, cut the next RC by
repeating the RC1 sequence with the next RC number (e.g. `13.2.0rc2`):
CHANGELOG, version bump, demo update, then push, tag, upload, and
announcement, with the same human checkpoints. Repeat for `rc3`, `rc4`,
etc. until you are confident the release is ready.

### Promote the final RC to the official release

Validation of an RC means at minimum one successful deployment test of the
RC tag via the `deployment-test` skill, with committed `analysis.md` files
(one per deployed app) whose verdicts recommend promotion (see step 9 of
the RC sequence). If the deployment test surfaced bugs, fix them and cut
another RC instead. Record a link to the deployment-test branch and its
`analysis.md` files in the release MR description.

Once the latest RC has been validated and no further changes are needed:

1. Consolidate the RC headings in `CHANGELOG.md` into a single final
   `# [13.2.0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0) Release - YYYY-MM-DD`
   section. If there are final-release fragments for changes since the latest
   RC, first run:

   ```bash
   psynet dev changelog release 13.2.0 YYYY-MM-DD
   ```

   Then review the generated/folded section and remove any now-empty
   intermediate RC headings.

2. [Bump the version](#bump-the-version) from `13.2.0rcN` to `13.2.0`.

3. [Update demo and test experiments](#update-demo-and-test-experiments).

4. Resume the minor release path from
   [step 4 (Create a merge request)](#4-create-a-merge-request) onwards
   to review the release MR, tag `v13.2.0` from the release branch,
   publish to PyPI, create the GitLab release, announce on Slack, and
   then merge the release branch back into `master`.

## Dallinger version considerations

If this release upgrades the Dallinger dependency:

- Update the Dallinger version specifier in `pyproject.toml`
  (e.g. `dallinger[docker]>=12.2.0,<13`).
- Update `recommended_dallinger_major_minor` in `psynet/version.py`.
- Make sure the correct Dallinger version is installed in your environment
  before running `psynet dev experiments update`, as the command uses it to
  resolve constraint versions.

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
  - `Update demo and test experiments for PsyNet X.Y.Z`
