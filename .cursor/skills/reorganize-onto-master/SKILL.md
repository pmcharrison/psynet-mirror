---
name: reorganize-onto-master
description: Reorganize a feature branch that already contains current master into logical commits with git reset --soft origin/master, then force-with-lease push. Use when the user asks to reorganize commits, group the branch into logical units, drop a merge commit, run /reorganize-onto-master, or after /branch-review of a just-merged tree.
---

# Reorganize Onto Master

Rebuild the current feature branch as a few logical commits on
`origin/master`. Use this **after** `/update-onto-master` and
`/branch-review`, once the merged tree is accepted.

The point is the commit grouping, not merely a straight-line history.
`git reset --soft origin/master` keeps the reviewed tree and moves
`HEAD` to `origin/master` so you can recommit that tree in sensible
units. It does **not** fetch or merge. If `origin/master` is not
already an ancestor of `HEAD`, stop and tell the user to run
`/update-onto-master` first. Soft-resetting a stale tree drops
master's new files.

## Prerequisites

1. Confirm you are on a feature branch, not `master`:
   `git rev-parse --abbrev-ref HEAD`
2. `git fetch origin master`
3. Stop if there are uncommitted changes to tracked files.
4. Confirm `git merge-base --is-ancestor origin/master HEAD`.
   If that fails, run `/update-onto-master` first.

## 1) Soft-reset onto master

```bash
git branch "<branch>-before-rewrite" HEAD
git reset --soft origin/master
```

The index and worktree stay at the reviewed merge result. `HEAD` is
now `origin/master`.

## 2) Recreate logical commits

Unstage if you need more than one commit (`git reset`), then `git add`
feature files in groups. Each commit should be one concern (for
example metadata, a dependency pin, CI, docs). Do not recommit
master's own changes — they are already the parent.

One commit is fine when the change is a single unit. Prefer a few
clear commits over replaying the original incremental history.

## 3) Push

```bash
git push --force-with-lease origin HEAD
```

Never force-push `master`. Leave the `<branch>-before-rewrite` backup
until the user is happy.
