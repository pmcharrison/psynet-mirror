# Update Onto Target

Use the project skill at `.cursor/skills/update-onto-target/SKILL.md`.

Read the open merge request's target branch from GitLab. Fetch
`origin/<target>` and fast-forward the local target, then merge that
into the feature branch and resolve every conflict. Push with a
regular `git push`. If there is no open MR, stop and ask; do not
assume `master`.

Do not soft-reset and do not review here. `/branch-review` runs this
skill first, then reviews. After the review, `/reorganize-onto-target`
rebuilds the tree as logical commits on the current target.
