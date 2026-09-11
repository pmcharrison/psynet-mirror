# Reorganize Onto Target

Use the project skill at `.cursor/skills/reorganize-onto-target/SKILL.md`.

After `/update-onto-target` and `/branch-review`, rebuild the accepted
tree as logical commits on the merge-request target with
`git reset --soft origin/<target>`, then force-with-lease push. Do
not merge here and do not fetch a newer target.
