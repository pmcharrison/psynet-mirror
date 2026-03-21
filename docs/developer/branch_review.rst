Branch review in Cursor
=======================

Cursor users can run ``/review`` for day-to-day branch reviews in the ``PsyNet``
repository.

Using ``/review``
+++++++++++++++++

#. Open Cursor chat while working in the ``PsyNet`` repository.
#. Type ``/review``.
#. Make sure your current branch is the feature branch you want to review.

If you are already on ``master``, switch to the branch you want to review first.

What ``/review`` does
+++++++++++++++++++++

* compares the current branch against ``master``
* follows the shared project workflow in ``.cursor/skills/branch-review/SKILL.md``
* returns findings first, followed by missing tests, refactoring opportunities,
  and residual risks

Reference workflow
++++++++++++++++++

The detailed review workflow lives in
``.cursor/skills/branch-review/SKILL.md``.
The command itself is defined in ``.cursor/commands/review.md``.
