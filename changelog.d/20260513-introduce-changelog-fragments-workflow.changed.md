Introduced a changelog-fragments workflow under `changelog.d/` to eliminate `CHANGELOG.md` merge conflicts between MRs. Each change now ships as a small markdown fragment, and `CHANGELOG.md` is generated from those fragments at release time. Highlights:

- Added the source-checkout-only `psynet dev changelog` command group, with `preview` to render fragments without changing files, `new <category> "<description>"` to create a date-prefixed fragment, and `release <version> <date>` to fold fragments into a versioned `CHANGELOG.md` section.
- Wired GitLab's merge-request changelog check through the installed `psynet dev changelog check-mr` command so CI validates fragments through the same source-checkout command path as maintainers.
- Supported categories follow Keep a Changelog ordering: `breaking`, `added`, `changed`, `deprecated`, `removed`, `fixed`, `updated`, `documentation`. Empty sections are skipped in the rendered output.
- Removed the in-progress `## Unreleased` section from `CHANGELOG.md` so future MRs don't conflict on it.
- Tightened the GitLab `changelog_check` CI job to enforce two rules on normal MRs: (1) the diff must touch a date-prefixed fragment file, and (2) `CHANGELOG.md` must not be edited directly. Release branches are exempt because they regenerate `CHANGELOG.md` from fragments.
- Documented the workflow, contributor expectations (commit only fragments, never a regenerated `CHANGELOG.md`), and the date-prefixed fragment convention in `AGENTS.md` and `changelog.d/README.md`.

(author: [Frank Höger])
