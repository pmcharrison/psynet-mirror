Introduced a changelog-fragments workflow under `changelog.d/` to eliminate `CHANGELOG.md` merge conflicts between MRs. Each change now ships as a small markdown fragment, and `CHANGELOG.md` is generated from those fragments at release time. Highlights:

- Added `docs/scripts/build_changelog.py` with commands to rebuild the `## Unreleased` block from fragments, create new fragments with `--new`, and cut releases with `--release <version> <date>` (which inserts a versioned section, clears `## Unreleased`, and deletes consumed fragments).
- Added a `--new <category> "<description>"` helper that creates a `<YYYYMMDD>-<slug>.<category>.md` fragment with a stub for editing, so contributors don't have to think about filename rules.
- Supported categories follow Keep a Changelog ordering: `breaking`, `added`, `changed`, `deprecated`, `removed`, `fixed`, `updated`, `documentation`. Empty sections are skipped in the rendered output.
- Migrated the historical `## Unreleased` block into 134 fragments using synthetic `9xxx` IDs, then cleared the rendered Unreleased section so future MRs don't conflict on it.
- Tightened the GitLab `changelog_check` CI job to enforce two rules on every MR: (1) the diff must touch a fragment file, and (2) `## Unreleased` in `CHANGELOG.md` must contain only the managed-block markers (no manual entries, no committed local rebuilds). Release MRs that delete fragments and clear Unreleased pass automatically.
- Documented the workflow, contributor expectations (commit only fragments, never a regenerated `CHANGELOG.md`), the date-based fallback for direct pushes to `master`, and the legacy numeric IDs in `AGENTS.md` and `changelog.d/README.md`.

(author: [Frank Höger])
