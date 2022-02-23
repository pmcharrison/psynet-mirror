.. _developer:
.. highlight:: shell

Releasing new versions
======================

#.
    After the ``dev`` branch has been merged into ``master``, update `CHANGELOG.md` if that hasn't been done
    as part of the work that is going into the new release.

    With semantic versioning, there are three parts to the version number, see https://semver.org/ for reference.
    When making a release you need to decide on the parts of the version number which should get bumped. It determines
    which command you give to ``bumpversion``: ``major`` is for breaking changes, ``minor`` for new features, ``patch`` for bug fixes.

    Example:
    Running ``bumpversion patch``, will change every mention of the current version in the codebase and increase it by `0.0.1`.

#.
    Commit and push the changes with "Release version X.Y.Z"

#.
    Finally, tag the commit with ``git tag vX.Y.Z`` and do ``git push origin --tags``.
