---
name: branch-review
description: Review branch changes against `master` using a diff-to-master workflow that emphasizes correctness, regressions, API breaks, side effects, and missing tests. Use when the user asks to review a branch against `master`, compare branch changes, perform pre-merge code review, or review a merge request.
---

# Branch Review

Use this skill when reviewing a feature branch against `master`.

Before reviewing, bring the branch onto current `origin/master` so the
reviewed diff is the real merge result, not a stale fork. Resolve every
conflict during that update; do not review a branch that is behind
`master`.

## Prerequisites

1. Verify you are not already on `master`:
   - `git rev-parse --abbrev-ref HEAD`
   - If the result is `master`, ask the user which branch to review.
2. Refresh the base branch:
   - `git fetch origin master`
3. Refuse to rewrite if there are uncommitted changes to tracked files.
   Untracked files may stay in the worktree.

## 1) Update onto current master

The review scope is `origin/master...HEAD`. That range is only meaningful
if `origin/master` is an ancestor of `HEAD`. Check with:

```bash
git merge-base --is-ancestor origin/master HEAD
```

If that succeeds **and** the branch has no merge commits
(`git rev-list --min-parents=2 --count origin/master..HEAD` is `0`),
skip this step. The branch is already a linear descendant of current
`master`.

Otherwise update it as follows. This is not a rebase of the old commits.

1. Merge current master so the working tree contains both sides, and
   resolve every conflict:

   ```bash
   git merge origin/master
   ```

   Do not abort because of conflicts. Resolve each conflicted file so
   the result is the intended combination of this branch and `master`,
   then complete the merge commit. If a conflict is a genuine product
   decision you cannot make, stop and ask the user; do not leave the
   merge half-finished.

2. Rewrite the updated tree as linear commits on current `master`.
   `git reset --soft origin/master` keeps the merged tree (index and
   worktree stay at the merge result) and moves `HEAD` to
   `origin/master`. Master's files are already in that tree from step 1;
   the soft reset does **not** fetch or merge them by itself. It only
   drops the merge commit and any earlier feature commits so they can
   be replaced:

   ```bash
   git branch "<branch>-before-rewrite" HEAD
   git reset --soft origin/master
   ```

3. Recreate the feature work as one or more logical commits from the
   staged tree (split mixed concerns when that is easy; otherwise one
   commit is fine). Do not recommit master's own changes — they are
   already the parent. Use `git reset` (mixed) to unstage, then `git add`
   the feature files in groups if you need more than one commit.

4. Force-with-lease push the rewritten branch so the merge request
   matches what you will review:

   ```bash
   git push --force-with-lease origin HEAD
   ```

   Never force-push `master`. Leave the `<branch>-before-rewrite`
   backup until the user is happy.

If the branch was already up to date but still had a merge commit, skip
the merge and start at the backup + soft-reset step.

## 2) Scope the change

The review scope is the committed branch diff in `origin/master...HEAD`.
Do not treat uncommitted local changes as part of the branch review.

- `git rev-parse --abbrev-ref HEAD` — confirm you are on the feature branch, not `master`
- `git diff --name-status origin/master...HEAD`
- `git diff --stat origin/master...HEAD`
- `git status --short` — if non-empty, note that untracked or leftover local files exist and were not included in the review

## 3) Inspect code diffs deeply

Review behavior-changing files first, especially core code and tests.

Check for:

- correctness bugs
- regressions
- breaking API behavior
- hidden side effects such as I/O, DB, network, or CLI changes

## 4) Validate test coverage

Behavior changes should typically be covered by tests, including:

- positive paths
- error paths
- edge cases

Look for missing tests around:

- mixed or invalid types
- empty or `None` values
- filename or path normalization
- platform-specific behavior

Avoid bloated tests, though: unless the area is particularly high risk,
recommend avoiding tests that are overly complex or long compared to the original code.

## 5) Refactoring opportunities

Flag:

- repetitive code
- mixed concerns in the same function or module
- unclear naming or missing docstrings
- dead code
- compatibility shims that may no longer be needed

## 6) Verification

- Run focused tests for changed areas when practical.
- If tests cannot run, say why and state the residual risk.

## 7) Report format

Present findings first, ordered by severity.

Use this structure:

1. Findings
2. Missing tests
3. Refactoring opportunities
4. Residual risks / assumptions

Keep summaries brief and make the primary feedback actionable.
