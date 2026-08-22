---
name: branch-review
description: Review branch changes against `master` using a diff-to-master workflow that emphasizes correctness, regressions, API breaks, side effects, and missing tests. Use when the user asks to review a branch against `master`, compare branch changes, perform pre-merge code review, or review a merge request.
---

# Branch Review

Use this skill when reviewing a feature branch against `master`.

This skill only reviews. It does not merge, rewrite, or push.

Order: `/update-onto-master` (merge and resolve conflicts), then this
review of that tree, then `/linearize-onto-master` (soft-reset) once
the tree is accepted. A merge commit is expected between those first
two steps.

## Prerequisites

1. Verify you are not already on `master`:
   - `git rev-parse --abbrev-ref HEAD`
   - If the result is `master`, ask the user which branch to review.
2. Refresh the base branch:
   - `git fetch origin master`
3. Confirm `origin/master` is an ancestor of `HEAD`:

   ```bash
   git merge-base --is-ancestor origin/master HEAD
   ```

   If that fails, do not review. Tell the user to run
   `/update-onto-master` first (merge current master and resolve
   conflicts). Resume this review after that command finishes.

   A merge commit is fine. Do not require a linear history here;
   `/linearize-onto-master` comes after the review.

## 1) Scope the change

The review scope is the committed branch diff in `origin/master...HEAD`.
Do not treat uncommitted local changes as part of the branch review.

- `git rev-parse --abbrev-ref HEAD` — confirm you are on the feature branch, not `master`
- `git diff --name-status origin/master...HEAD`
- `git diff --stat origin/master...HEAD`
- `git status --short` — if non-empty, note that uncommitted work exists locally and was not included in the review

## 2) Inspect code diffs deeply

Review behavior-changing files first, especially core code and tests.

Check for:

- correctness bugs
- regressions
- breaking API behavior
- hidden side effects such as I/O, DB, network, or CLI changes

## 3) Validate test coverage

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

## 4) Refactoring opportunities

Flag:

- repetitive code
- mixed concerns in the same function or module
- unclear naming or missing docstrings
- dead code
- compatibility shims that may no longer be needed

## 5) Verification

- Run focused tests for changed areas when practical.
- If tests cannot run, say why and state the residual risk.

## 6) Report format

Present findings first, ordered by severity.

Use this structure:

1. Findings
2. Missing tests
3. Refactoring opportunities
4. Residual risks / assumptions

Keep summaries brief and make the primary feedback actionable.

If the review is acceptable and
`git rev-list --min-parents=2 --count origin/master..HEAD` is not `0`,
tell the user to run `/linearize-onto-master` next.
