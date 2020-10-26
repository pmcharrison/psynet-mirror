.. _developer:
.. highlight:: shell

================
Working with git
================

When working on shared projects together, Git branching helps to organise the
code such that code conflicts are minimized. So if need be, this is the time to
make yourself comfortable with using Git by working through one of the many
tutorials freely available on the net.

The PsyNet development team has adopted the following branching model for how
the code is organised in Git:

The ``master`` branch is the most public-facing version of the repository. It is
the most stable form of the code, and we should be confident that whatever
functionality is implemented there works well. Each change to the master branch
will typically correspond to a new version number (see https://semver.org/ for 
versioning conventions).

The ``dev`` branch constitutes the next version of the software that is being
prepared for release. It is iteratively developed until it is ready to make a new
release. New releases are made by merging the ``dev`` branch into the ``master``
branch or for short: 'merging ``dev`` *into* ``master``'.

In practice, many people will be preparing changes to the ``dev`` branch simultaneously.
So, if everybody was to work directly on ``dev``, this would cause conflicts.
Instead, when you want to contribute code to ``dev``, you should begin by creating a
*feature branch*, which branches off of the current state of ``dev``, where you work
independently on your contribution. When you're done with the contribution,
then you merge it into ``dev``, and delete the feature branch.
It is possible to perform merges with the ``git merge`` command.
However, in team projects, one should instead perform merges using the *Merge Request*
functionality in GitLab. This presents the proposed merge to the rest of your team
and allows them to comment on it before accepting it. This is a useful
point at which they can perform code review.

The next section will exemplify the Git development workflow by using Git'S CLI
together with the steps necessary in GitLab.
