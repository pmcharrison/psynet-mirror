---
name: update-onto-master
description: Merge current origin/master into the feature branch and resolve every conflict so the working tree is the real merge result. Use when the user asks to update onto master, sync with master, or run /update-onto-master, and as the first step of /branch-review.
---

# Update Onto Master

Merge current `origin/master` into the feature branch and resolve every
conflict. This is a write, not a review, and it does **not** rewrite
history.

The tree after this command is what will land. `/branch-review` runs
this skill first, then reviews that tree. Soft-reset is
`/reorganize-onto-master` and comes last: it does not fetch or merge,
so running it without this merge first drops master's new work.

## Prerequisites

1. Confirm you are on a feature branch, not `master`:
   `git rev-parse --abbrev-ref HEAD`
2. Refresh remote and local `master` without checking it out:

   ```bash
   git fetch origin master:master
   ```

   That updates `origin/master` and fast-forwards local `master`. Stay
   on the feature branch. If the fetch fails because local `master`
   has diverged, run `git fetch origin master` only, leave local
   `master` alone, merge `origin/master` into this branch, and tell
   the user local `master` was not moved.
3. Stop if there are uncommitted changes to tracked files. Untracked
   files may stay in the worktree.

If `git merge-base --is-ancestor origin/master HEAD` already succeeds,
say so and stop. The branch already contains current `master`. If it
still has a merge commit or a messy commit list, the next step after
review is `/reorganize-onto-master`, not another merge.

## Merge current master

```bash
git merge origin/master
```

Resolve every conflict. Do not abort because files conflict. The result
must be the intended combination of this branch and `master`. Complete
the merge commit. If a conflict is a product decision you cannot make,
stop and ask the user; do not leave the merge half-finished.

Push the merge with a regular `git push` (not force). Never force-push
`master`.

If this skill was invoked on its own, typical next step is
`/branch-review` (which will no-op the merge if `master` is already
an ancestor). After that review, run `/reorganize-onto-master` to
rebuild the tree as logical commits.
