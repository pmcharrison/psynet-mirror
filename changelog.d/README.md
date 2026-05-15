# Changelog Fragments

Add one changelog fragment per change in this directory. The recommended
way to create one is:

```bash
python docs/scripts/build_changelog.py --new <category> "<short description>"
```

This writes a uniquely-named fragment file containing your description as a
stub, which you then edit to the final entry.

## Filename format

`<id>.<category>.md`

Where `<id>` is any alphanumeric token (with `_` or `-`) that uniquely
identifies the fragment. The `--new` helper generates IDs of the form
`<YYYYMMDD>-<slug>`. The date prefix keeps fragments roughly
chronological and the slug differentiates same-day fragments;
the helper refuses to overwrite an existing file, so use a more
specific description if it complains. Hand-rolled IDs (numbers,
branch slugs, plain descriptive slugs, etc.) are also valid as long
as they are unique within `changelog.d/`.

Supported categories (rendered in this order):

- `breaking` → **Breaking Changes**
- `added` → **Added**
- `changed` → **Changed**
- `deprecated` → **Deprecated**
- `removed` → **Removed**
- `fixed` → **Fixed**
- `updated` → **Updated**
- `documentation` → **Documentation**

Fragment contents should be a single changelog entry in markdown without a
leading `-`.

Examples:

- `20260513-add-chatroom-demo.added.md`
- `20260513-fix-selenium-flake.fixed.md`
- `20260514-deprecate-old-helper.deprecated.md`

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
catch missing fragments on direct pushes to `master`. If you push
directly to `master` (bypassing an MR), please still create a fragment
with the `--new` helper so the change appears in the next release notes.
Its date-prefixed filenames stay unique as long as slugs differ on the
same day.

## Legacy IDs

The directory currently also contains fragments with bare numeric IDs:

- `9xxx.<category>.md` — one-shot synthetic IDs used when the
  historical `## Unreleased` block was migrated into fragments.
- `<MR-number>.<category>.md` — older MR-numbered fragments from before
  the slug-based convention.

These remain valid and will be consumed at the next release. Please use
the `--new` helper for all new fragments going forward.
