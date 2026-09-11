# Reorganize Onto Target

Use the project skill at `.cursor/skills/reorganize-onto-target/SKILL.md`.

Run this just before the merge request is merged into its target.
Rebuild the current feature branch as logical commits on that target
with `git reset --soft origin/<target>`, then force-with-lease push.
Do not merge here and do not fetch a newer target. If the target is not
already an ancestor of `HEAD`, stop and tell the user to run
`/update-onto-target` first.
