# Changelog Fragments

Add one changelog fragment per merge request in this directory.

Filename format: `<merge-request-number>.<category>.md`

Supported categories (rendered in this order):

- `breaking` → **Breaking Changes**
- `added` → **Added**
- `changed` → **Changed**
- `deprecated` → **Deprecated**
- `removed` → **Removed**
- `fixed` → **Fixed**
- `updated` → **Updated**
- `documentation` → **Documentation**

Fragment contents should be a single changelog entry in markdown without a leading `-`.

Examples:

- `1842.added.md`
- `1849.fixed.md`
- `1851.documentation.md`
- `1860.breaking.md`
- `1865.updated.md`
- `1870.deprecated.md`

## Workflow

Contributors commit **only** the fragment file in their MR, never a
regenerated `CHANGELOG.md`. `CHANGELOG.md` is a generated artifact and
its `## Unreleased` block is rebuilt by the maintainer at release time;
committing it from MRs would re-introduce the merge-conflict problem
that fragments are designed to prevent.

If you want to preview how your fragment will render, run the script
locally and discard the resulting `CHANGELOG.md` change before pushing:

```bash
python docs/scripts/build_changelog.py
git restore CHANGELOG.md
```

Maintainers cut a release from the current fragments with:

```bash
python docs/scripts/build_changelog.py --release 13.2.0 2026-03-13
```

This inserts a new `## [13.2.0]` section, clears `## Unreleased`, and
deletes the consumed fragments.

## Direct pushes to `master`

The `changelog_check` CI job only runs on merge requests, so it cannot
catch missing fragments on direct pushes to `master`. Even a one-commit
change should go through an MR so CI can verify the fragment.

If you absolutely must push directly to `master`, add a fragment in the
same commit using a date-based identifier (`YYYYMMDD.<category>.md`),
for example `20260507.fixed.md`. 8-digit dates start at `20260000+`,
well clear of real MR numbers and the synthetic `9xxx` migration IDs,
so collisions are effectively impossible.
