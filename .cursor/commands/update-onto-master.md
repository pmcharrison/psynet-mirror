# Update Onto Master

Use the project skill at `.cursor/skills/update-onto-master/SKILL.md`.

Fetch `origin/master` and fast-forward local `master` (`git fetch
origin master:master`), then merge that into the feature branch and
resolve every conflict. Push with a regular `git push`.

Do not soft-reset and do not review here. `/branch-review` runs this
skill first, then reviews. After the review, `/reorganize-onto-master`
rebuilds the tree as logical commits on current `master`.
