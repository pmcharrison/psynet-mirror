.. _developer:
.. highlight:: shell

==============
Basic workflow
==============

Before starting to contribute to PsyNet you need to carry out a developer installation on your local computer. Follow the instructions in :ref:`Developer installation` and come back here once you are done.

Make sure to have read through :ref:`Working with Git` in the previous section which outlines the Git model the PsyNet development process is based on.

#.
  Create a new Jira issue which will have an identifier like ``CAP-123`` and add a complete as possible specification of the implementation.

  ..
    See :ref:`Working with Jira` for more details (TODO).

#.
  Change into your local ``psynet`` project directory and use the identifier of the Jira issue to create a new Git branch, e.g.:

  .. code-block:: console

    cd ~/cap
    git checkout -b CAP-123_<add-new-feature> master

  *\*Replace <add-new-feature> with an appropriate short phrase describing the issue you will be working on.* Note: Use hyphens to join two or more words.

  This will create a new branch ``CAP-123_<add-new-feature>`` by branching off of the master branch which represents the current stable version of PsyNet. In case you want to use the ``dev`` branch as your code basis possibly including new unreleased features and bugfixes simply replace ``master`` with ``dev``:

  .. code-block:: console

    cd ~/cap
    git checkout -b CAP-123_<add-new-feature> dev

  The above command will automatically also change the working branch to the newly created branch. For initially pushing this new branch to GitLab execute following in your console:

  .. code-block:: console

    git push --set-upstream origin CAP-123_<add-new-feature>

#.
  Load the virtual environment in case you haven't yet, e.g.:

  .. code-block:: console

    workon dlgr_env

  You should now be all set up to start coding.

#.
  Implement your code until you're happy; discuss implementation questions with colleagues using GitLab's code review components. If you make changes to the implementation details, document them in the merge request, not in the issue itself. Regularly ``commit`` and ``push`` your changes to the ``psynet`` Git repository, e.g.:

  .. code-block:: console

    git add <filename-1> <filename-2>
    git commit -m "Add new feature"
    git push

  Once you think it is time to have others take a look at the code create a *merge request* in Gitlab.

#. 
  Create a merge request in GitLab.
  
  a.
    Login into GitLab and create a new `merge request` by first navigating to ``Merge Requests`` in the GitLab menu and then clicking the blue ``Create merge request`` button on the top right.

  #.
    On the next page change the target branch to ``dev`` by clicking on the ``Change branches`` link and selecting ``dev`` in the `Target branch` box. Click ``Compare branches and continue``.

  #.
    Optionally, edit the title of the merge request by at least prefixing it with ``WIP:`` to signal that this is a work-in-progress which prevents the merge request from being merged before it's ready.

  #. 
    Optionally, increment the number of approvers. 

    *Enforcing approval is not mandatory but should be considered best practice. Using the feature promotes better control of the development process.*

  #. 
    Finally click the ``Submit merge request`` button.

#.
  Continue pushing code to the repository in GitLab by leveraging its code view capabilities to get feedback from your colleagues iteratively improving on code quality.

#.
  Fix possible merge conflicts if necessary.

#.
  Once the code was approved by a member of your team mark the merge request as being `ready` by clicking the ``Mark as ready`` button.

#.
  Under `Merge options` tick the ``Squash commits when merge request is accepted.`` checkbox in case you have a number of commits that you want to pack into one single commit. Squashing commits results in a cleaner Git commit history.

#.
  Finally, merge your code into the target branch by clicking the green ``Merge`` button.
