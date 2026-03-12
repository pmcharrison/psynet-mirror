# Diff-To-Master Review Checklist

Cursor users: run `/review` for day-to-day reviews. It uses the shared project workflow in `.cursor/skills/review-merge-request/SKILL.md`. Use this document as the reference version of the same workflow.

Use this checklist when asked to review branch changes against `master`.

## Prerequisites

- Run `git rev-parse --abbrev-ref HEAD` to verify you are on a feature branch, not `master`.
  If you are on `master`, ask the user which branch to review.
- Fetch the latest `master` so diffs are accurate: `git fetch origin master`

## 1) Scope the change

- `git rev-parse --abbrev-ref HEAD` — confirm you are on the feature branch, not `master`
- `git diff --name-status master...HEAD`
- `git diff --stat master...HEAD`
- `git diff --name-status master`

## 2) Inspect code diffs deeply

- Review behavior-changing files first (core code + tests).
- Check for:
  - correctness bugs
  - regressions
  - breaking API behavior
  - hidden side effects (I/O, DB, network, CLI)

## 3) Validate test coverage

- Ensure each behavior change has:
  - positive-path tests
  - error-path tests
  - edge-case tests
- Look for missing tests around:
  - mixed/invalid types
  - empty/None values
  - filename/path normalization
  - platform-specific behavior

## 4) Refactoring opportunities

- Flag repetitive or mixed-concern code.
- Suggest clearer naming/docstrings where needed.
- Identify dead code and compatibility shims.

## 5) Verification

- Run focused tests for changed areas.
- If tests cannot run, state why and list residual risk.

## 6) Report format

1. Findings (highest severity first)
2. Missing tests
3. Refactoring opportunities
4. Residual risks / assumptions
