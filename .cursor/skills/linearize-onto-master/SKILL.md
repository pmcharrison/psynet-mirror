---
name: linearize-onto-master
description: Rewrite a feature branch that already contains current master as linear commits with git reset --soft origin/master, then force-with-lease push. Use when the user asks to linearize the branch, drop a merge commit, run /linearize-onto-master, or after /branch-review of a just-merged tree.
---

# Linearize Onto Master

Rewrite the current feature branch so it is a linear descendant of
`origin/master`. Use this **after** `/update-onto-master` and
`/branch-review`, once the merged tree is accepted.

`git reset --soft origin/master` keeps the current tree and moves
`HEAD` to `origin/master`. It does **not** fetch or merge. If
`origin/master` is not already an ancestor of `HEAD`, stop and tell
the user to run `/update-onto-master` first. Soft-resetting a stale
tree drops master's new files.

## Prerequisites

1. Confirm you are on a feature branch, not `master`:
   `git rev-parse --abbrev-ref HEAD`
2. `git fetch origin master`
3. Stop if there are uncommitted changes to tracked files.
4. Confirm `git merge-base --is-ancestor origin/master HEAD`.
   If that fails, run `/update-onto-master` first.
5. If `git rev-list --min-parents=2 --count origin/master..HEAD` is
   `0`, the branch is already linear. Say so and stop.

## 1) Soft-reset onto master

```bash
git branch "<branch>-before-rewrite" HEAD
git reset --soft origin/master
```

The index and worktree stay at the reviewed merge result. `HEAD` is
now `origin/master`.

## 2) Recreate feature commits

Recreate the feature work as one or more logical commits from the
staged tree. Split mixed concerns when that is easy; otherwise one
commit is fine. Do not recommit master's own changes — they are
already the parent.

To split: `git reset` (mixed) to unstage, then `git add` feature files
in groups.

## 3) Push

```bash
git push --force-with-lease origin HEAD
```

Never force-push `master`. Leave the `<branch>-before-rewrite` backup
until the user is happy.
