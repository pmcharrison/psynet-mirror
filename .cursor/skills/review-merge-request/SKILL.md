---
name: review-merge-request
description: Review branch changes against `master` using a diff-to-master workflow that emphasizes correctness, regressions, API breaks, side effects, and missing tests. Use when the user asks to review a merge request, review a branch against `master`, or perform code review on pending branch changes.
---

# Review Merge Request

Use this skill when reviewing a feature branch against `master`.

## Quick Start

1. Verify you are not already on `master`:
   - `git rev-parse --abbrev-ref HEAD`
   - If the result is `master`, ask the user which branch to review.
2. Refresh the base branch:
   - `git fetch origin master`
3. Scope the review:
   - `git diff --name-status master...HEAD`
   - `git diff --stat master...HEAD`
   - `git diff --name-status master`

## Review Focus

Review behavior-changing files first, especially core code and tests.

Check for:

- correctness bugs
- regressions
- breaking API behavior
- hidden side effects such as I/O, DB, network, or CLI changes

## Test Coverage

For each behavior change, verify coverage for:

- positive paths
- error paths
- edge cases

Look for missing tests around:

- mixed or invalid types
- empty or `None` values
- filename or path normalization
- platform-specific behavior

## Refactoring Signals

Flag:

- repetitive code
- mixed concerns in the same function or module
- unclear naming or missing docstrings
- dead code
- compatibility shims that may no longer be needed

## Verification

- Run focused tests for changed areas when practical.
- If tests cannot run, say why and state the residual risk.

## Report Format

Present findings first, ordered by severity.

Use this structure:

1. Findings
2. Missing tests
3. Refactoring opportunities
4. Residual risks / assumptions

Keep summaries brief and make the primary feedback actionable.
