# Update Onto Master

Use the project skill at `.cursor/skills/update-onto-master/SKILL.md`.

Merge current `origin/master` and resolve every conflict, then
`git reset --soft origin/master` and recommit so the branch is a linear
descendant of `master`. Force-with-lease push the result.

Do not review the branch here. After the update, the user can run
`/branch-review`.
