# Branch Review

Use the shared project skill at `.cursor/skills/branch-review/SKILL.md` to review the current branch against `master`.

Apply that skill's workflow and report format in full. If the branch is
behind `master`, stop and tell the user to run `/update-onto-master`
first. After an acceptable review, tell them to run
`/linearize-onto-master` if the history still has a merge commit.
