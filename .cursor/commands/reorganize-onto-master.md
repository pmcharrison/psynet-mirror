# Reorganize Onto Master

Use the project skill at `.cursor/skills/reorganize-onto-master/SKILL.md`.

After `/update-onto-master` and `/branch-review`, rebuild the accepted
tree as logical commits on current `master` with
`git reset --soft origin/master`, then force-with-lease push. Do not
merge here.
