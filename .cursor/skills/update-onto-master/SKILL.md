---
name: update-onto-master
description: Merge current origin/master into the feature branch, resolve conflicts, then git reset --soft origin/master and recommit so the branch is a linear descendant of master. Use when the user asks to update onto master, sync with master, linearize the branch, run /update-onto-master, or when /branch-review refuses because the branch is behind master or still has a merge commit.
---

# Update Onto Master

Bring the current feature branch onto current `origin/master` and leave it
linear. This is a write: it merges, rewrites commits, and force-with-lease
pushes. It is not a review.

Do **both** steps, in this order:

1. **Merge** `origin/master` so the tree contains master's new files.
2. **`git reset --soft origin/master`** and recommit so the merge commit
   disappears and the MR is a linear descendant of `master`.

Soft reset does not fetch or merge. It only keeps the current tree and
moves `HEAD` to `origin/master`. Running it without the merge first
drops master's new work.

## Prerequisites

1. Confirm you are on a feature branch, not `master`:
   `git rev-parse --abbrev-ref HEAD`
2. `git fetch origin master`
3. Stop if there are uncommitted changes to tracked files. Untracked
   files may stay in the worktree.

If the branch is already a linear descendant of current `master`
(`git merge-base --is-ancestor origin/master HEAD` succeeds **and**
`git rev-list --min-parents=2 --count origin/master..HEAD` is `0`),
say so and stop. Do not rewrite SHAs for no reason.

## 1) Merge current master

```bash
git merge origin/master
```

Resolve every conflict. Do not abort because files conflict. The result
must be the intended combination of this branch and `master`. Complete
the merge commit. If a conflict is a product decision you cannot make,
stop and ask the user; do not leave the merge half-finished.

If the branch already contains `origin/master` but still has a merge
commit, skip this step and go to the soft reset.

## 2) Soft-reset onto master

```bash
git branch "<branch>-before-rewrite" HEAD
git reset --soft origin/master
```

The index and worktree stay at the merged tree. `HEAD` is now
`origin/master`. Master's files are already in that tree from step 1.

## 3) Recreate feature commits

Recreate the feature work as one or more logical commits from the staged
tree. Split mixed concerns when that is easy; otherwise one commit is
fine. Do not recommit master's own changes — they are already the parent.

To split: `git reset` (mixed) to unstage, then `git add` feature files
in groups.

## 4) Push

```bash
git push --force-with-lease origin HEAD
```

Never force-push `master`. Leave the `<branch>-before-rewrite` backup
until the user is happy.

Typical next step is `/branch-review`.
