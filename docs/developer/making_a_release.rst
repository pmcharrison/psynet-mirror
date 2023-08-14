.. _developer:
.. highlight:: shell

================
Making a release
================

PsyNet releases are made periodically by the core developers. There is no real rule about how often these releases are made; it comes down to a balance between making new features available early and avoiding spamming PsyNet users with too many updates to keep track of.

After all changes to be released have been merged into the ``master`` branch follow these steps:

#. Decide on an upgrade type for the new release following `semantic versioning guidelines <https://semver.org/>`_. The upgrade type can be one of the following:

    a. Major (new version includes breaking changes)

    b. Minor (new version includes only new features and/or bugfixes)

    c. Patch (new version includes only bugfixes)

#. Create a release branch from the ``master`` branch on your local machine: ``git checkout -b release-X.Y.Z``.
#. Using the GitLab interface identify the merge requests that contributed to the current ``master`` branch since the last release. The last release can easily be identified by its release tag, e.g. ``v10.1.0``.
#. Check that each merged merge request contains a populated CHANGELOG entry in its description. If any CHANGELOG entries are missing, notify the relevant contributors.
#. Combine the new CHANGELOG entries into PsyNet’s CHANGELOG.md file, updating any formatting as necessary.
#. Go through all the merge requests and close their associated issues with a comment linking them to the merge request: ‘Implemented in !XYZ’ where ‘XYZ’ is the merge request ID.
#. Update PsyNet’s version number in following files:

    * `pyproject.toml`

    * `psynet/version.py`

#. Write the new version number as the title of the new CHANGELOG entry.
#. Commit the changes to the CHANGELOG with the title ‘Release version X.Y.Z’.
#. Update the demos' `constraints.txt` files by executing ``python3 demos/update_demos.py`` from inside PsyNet's root directory. This could take a while depending on the processing power of your system.
#. Commit and push the changes made to the files inside the `demos` directory.
#. Create a merge request using GitLab's interface to merge the release branch into ``master`` and name it 'Release version X.Y.Z'. You might want to inspect for a last time the code changes for the release using the 'Changes' tab of the merge request.
#. Merge the release branch to ``master`` via the GitLab interface by choosing a simple merge commit (do not squash merge!).
#. On your local computer checkout the ``master`` branch and pull the changes.
#. Create a new tag corresponding to the new version number: ``git tag vX.Y.Z``.
#. Push the tag with ``git push --tags``.
#. Create a new PsyNet release using GitLab's interface under 'Deployments > Releases'.
#. Run following commands to publish the new release on PyPi (you need to have the `twine` package installed; install/upgrade it with ``python3 -m pip install --upgrade twine`` if you haven't yet):

    .. code-block:: console

        python3 -m build
        python3 -m twine upload --repository pypi dist/psynet-X.Y.Z*

    The new PsyNet release should now be published on PyPi (https://pypi.org/project/psynet/).
