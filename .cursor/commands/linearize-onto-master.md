# Linearize Onto Master

Use the project skill at `.cursor/skills/linearize-onto-master/SKILL.md`.

After `/update-onto-master` and `/branch-review`, rewrite the accepted
tree with `git reset --soft origin/master`, recommit in logical units,
and force-with-lease push. Do not merge here.
