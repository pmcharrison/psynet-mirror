# Changelog Fragments

Add one changelog fragment per merge request in this directory.

Filename format: `<merge-request-number>.<category>.md`

Supported categories (rendered in this order):

- `breaking` → **Breaking Changes**
- `added` → **Added**
- `changed` → **Changed**
- `updated` → **Updated**
- `deprecated` → **Deprecated**
- `removed` → **Removed**
- `fixed` → **Fixed**
- `documentation` → **Documentation**

Fragment contents should be a single changelog entry in markdown without a leading `-`.

Examples:

- `1842.added.md`
- `1849.fixed.md`
- `1851.documentation.md`
- `1860.breaking.md`
- `1865.updated.md`
- `1870.deprecated.md`

Regenerate `CHANGELOG.md` with:

```bash
python docs/scripts/build_changelog.py
```

Cut a release from the current fragments and clear `## Unreleased` with:

```bash
python docs/scripts/build_changelog.py --release 13.2.0 2026-03-13
```
