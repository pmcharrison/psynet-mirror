.. _developer:
.. highlight:: shell

================
Making a release
================

PsyNet releases are made periodically by the core developers. There is no real rule about how often these releases are made; it comes down to a balance between making new features available early and avoiding spamming PsyNet users with too many updates to keep track of.

After all changes to be released have been merged into the ``master`` branch follow these steps:

1. Decide on a version number for the new release following `semantic versioning guidelines <https://semver.org/>`_. The upgrade type can be one of the following:

    X. **Major** (new version includes breaking changes)

    Y. **Minor** (new version includes only new features and/or bugfixes)

    Z. **Patch** (new version includes only bugfixes)

2. Create a release branch from the ``master`` branch on your local machine:

.. code-block:: console

    git checkout -b release-X.Y.Z

3. Update the CHANGELOG:

    #. Using the GitLab interface identify the merge requests that contributed to the current ``master`` branch since the last release. The last release can easily be identified by its release tag, e.g. ``v10.1.0``. Check that each merged merge request contains a populated CHANGELOG entry in its description. If any CHANGELOG entries are missing, notify the relevant contributors.

    #. Combine the new CHANGELOG entries into PsyNet’s CHANGELOG.md file, updating any formatting as necessary.

    #. Go through all the merge requests and close their associated issues with a comment linking them to the merge request: ‘Implemented in !ABC’ where ‘ABC’ is the merge request ID.

    #. Write the new version number as the title of the new CHANGELOG entry.

    #. Commit the changes with

    .. code-block:: console

        git commit -m "Update CHANGELOG for version X.Y.Z"

4. Update PsyNet’s version number in following files:

    * `pyproject.toml`
    * `psynet/version.py`

and commit the changes with

.. code-block:: console

  git commit -m "Bump version to X.Y.Z"

5. Update the demos' `constraints.txt` files by executing

.. code-block:: console

    python3 demos/update_demos.py

from inside PsyNet's root directory. This could take a while depending on the processing power of your system.

.. attention::

    Before running the update script make sure to have checked out the version tag of Dallinger's latest release inside your Dallinger directory as otherwise the generated constraints.txt files will be incorrect!

Commit the changes with

.. code-block:: console

    git commit -m "Update demos for version X.Y.Z"

6. Push the changes to the release branch.
7. Create a merge request using GitLab's interface to merge the release branch into ``master`` and name it 'Release version X.Y.Z'. You might want to inspect for a last time the code changes for the release using the 'Changes' tab of the merge request.
8. Merge the release branch to ``master`` via the GitLab interface by choosing a simple merge commit (do not squash merge!).
9. On your local computer checkout the ``master`` branch and pull the changes:

.. code-block:: console

    git checkout master
    git pull

10. Create a new tag corresponding to the new version number:

.. code-block:: console

    git tag vX.Y.Z

11. Push the tag with

.. code-block:: console

    git push --tags

12. Create a new PsyNet release using GitLab's interface under *Deployments > Releases*.
13. Publish the new release on PyPi

.. note::

    You need to have the `twine` package installed; install/upgrade it with ``python3 -m pip install --upgrade twine`` if you haven't yet)

.. code-block:: console

    python3 -m build
    python3 -m twine upload --repository pypi dist/psynet-X.Y.Z*

The new PsyNet release should now be published on PyPi at https://pypi.org/project/psynet/.
