---
name: reorganize-onto-target
description: >-
  Rebuild a PsyNet feature branch as logical commits on the open GitLab
  merge-request target with git reset --soft, then force-with-lease
  push. Use when the user asks to reorganize commits or run
  /reorganize-onto-target. Does not fetch a newer target. Not part of
  /branch-review.
---

# Reorganize Onto Target

Rebuild the current feature branch as a few logical commits on the
open merge request's **target**. Use this when the user asks to
reorganize, not as a follow-up that `/branch-review` always runs.
The target must already be an ancestor of `HEAD`; if it is not, run
`/update-onto-target` first.

The point is the commit grouping, not merely a straight-line history.
`git reset --soft origin/<target>` keeps the reviewed tree and moves
`HEAD` to that target so you can recommit in sensible units.

This skill does **not** merge. It also must **not** fetch a newer
target and then soft-reset onto it: that would drop work that was never
reviewed. If `origin/<target>` is not already an ancestor of `HEAD`,
stop and tell the user to run `/update-onto-target` first.

## Resolve the target

Same source of truth as update-onto-target: the open MR's
`target_branch`. See `.cursor/skills/update-onto-target/SKILL.md`
(Resolve the target). Do not assume `master`.

## Prerequisites

1. Confirm you are on a feature branch, not the target:
   `git rev-parse --abbrev-ref HEAD`
2. Stop if there are uncommitted changes to tracked files.
3. Confirm `git merge-base --is-ancestor origin/<target> HEAD`.
   If that fails, run `/update-onto-target` first. Do not
   `git fetch` the target here.

## 1) Soft-reset onto the target

```bash
git branch "<branch>-before-rewrite" HEAD
git reset --soft "origin/$target"
```

The index and worktree stay at the reviewed merge result. `HEAD` is
now `origin/<target>`.

## 2) Recreate logical commits

Unstage if you need more than one commit (`git reset`), then `git add`
feature files in groups. Each commit should be one concern (for
example metadata, a dependency pin, CI, docs). Do not recommit the
target's own changes — they are already the parent.

One commit is fine when the change is a single unit. Prefer a few
clear commits over replaying the original incremental history.

## 3) Push

```bash
git push --force-with-lease origin HEAD
```

Never force-push the target branch. Leave the
`<branch>-before-rewrite` backup until the user is happy.
