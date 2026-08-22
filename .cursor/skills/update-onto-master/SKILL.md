---
name: update-onto-master
description: Merge current origin/master into the feature branch and resolve every conflict so the working tree is the real merge result. Use when the user asks to update onto master, sync with master, run /update-onto-master, or when /branch-review refuses because the branch is behind master.
---

# Update Onto Master

Merge current `origin/master` into the feature branch and resolve every
conflict. This is a write, not a review, and it does **not** rewrite
history.

The tree after this command is what will land. Review it with
`/branch-review` before linearizing. Soft-reset is `/linearize-onto-master`
and comes last: it does not fetch or merge, so running it without this
merge first drops master's new work.

## Prerequisites

1. Confirm you are on a feature branch, not `master`:
   `git rev-parse --abbrev-ref HEAD`
2. `git fetch origin master`
3. Stop if there are uncommitted changes to tracked files. Untracked
   files may stay in the worktree.

If `git merge-base --is-ancestor origin/master HEAD` already succeeds,
say so and stop. The branch already contains current `master`. If it
still has a merge commit, the next step after review is
`/linearize-onto-master`, not another merge.

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

Typical next step is `/branch-review`. After that review, run
`/linearize-onto-master` if the history still has a merge commit.
