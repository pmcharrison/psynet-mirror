# Update Onto Master

Use the project skill at `.cursor/skills/update-onto-master/SKILL.md`.

Merge current `origin/master` and resolve every conflict so the branch
tree is the real merge result. Push with a regular `git push`.

Do not soft-reset and do not review here. `/branch-review` runs this
skill first, then reviews. After the review, `/reorganize-onto-master`
rebuilds the tree as logical commits on current `master`.
