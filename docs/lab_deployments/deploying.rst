Deploying
=========

Sanity check
------------

Version control
^^^^^^^^^^^^^^^

Before you deploy your experiment, you need to:

-  Have a Git repository. If the experiment is not yet in Git, create a
   repository with:

   .. code:: bash

      git init

-  Commit all changes. There should be no staged or modified files when
   you deploy.

-  Define a remote repository and push your commits to it.

See :doc:`Prerequisites <prerequisites>` for Git setup instructions.

Updating PsyNet in Your Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When there are new commits in the PsyNet repository, you can update your
local installation in your virtual environment by following these steps:

1. **Go to the PsyNet Directory**

.. code:: bash

   cd ~/psynet

2. **Check Your Branch and Switch if Necessary**

Before pulling updates, confirm which branch you're on. If you need a
different version, check the current branch and switch accordingly:

.. code:: bash

   git branch  # Lists branches and highlights the current one

.. code:: bash

   git checkout <branch_name>  # Switch to the desired branch if needed

3. **Pull the Latest Changes**

.. code:: bash

   git pull

This command fetches and integrates the latest commits from the remote
repository.

4. **Verify the Latest Commit**

.. code:: bash

   git log

Check the commit messages and hashes to ensure you have the most recent
commit.

5. **Update your requirements.txt**

Once you have confirmed the latest commit, update the version or commit
hash reference in ``requirements.txt`` if the experiment points to a
specific PsyNet commit or branch. This keeps the deployment environment
aligned with the version you tested locally.

6. **Install the Updated Requirements**

.. code:: bash

   pip install -r requirements.txt

This command installs any new dependencies and updates existing ones as
necessary.

7. **Generate Constraints**

   .. code:: bash

      psynet generate-constraints

Requirements and dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure your local PsyNet (and Dallinger) version is the same as the
version listed in ``requirements.txt`` (otherwise you will get an error
when you try to deploy later). Usually, updating PsyNet to the latest
version used by your experiment helps deployment run smoothly.

Also, generate the constraints using ``psynet generate-constraints``.
Remember to run this command again if you make any changes to
``requirements.txt``.

Also test your experiment locally before trying it on the server. This
helps catch dependencies that are missing from ``requirements.txt``.
For a virtual-environment installation:

.. code:: bash

   psynet debug local

For a Docker installation (see the
`Docker installation guide <https://psynetdev.gitlab.io/PsyNet/installation/docker_installation/index.html>`__):

.. code:: bash

   bash docker/psynet debug local

Make sure the experiment has been sufficiently tested. See
`Test <general_deployment_process.html#test>`__.

Remote debug
^^^^^^^^^^^^

Before deployment, you need to make sure your experiment runs
successfully on a remote server. Make sure you did all types of
`tests <general_deployment_process.html#test>`__ and thus did a remote debug.

Actual deployment
-----------------

-  Set up the experiment for live deployment. For example, restore the
   production number of trials or networks if you reduced them during
   hotair testing.

-  Set the ``recruiter`` config parameter to the intended live recruiter,
   for example ``prolific`` or ``lucid``. Note: PsyNet still uses the
   name ``lucid`` internally for CINT deployments; consult the
   :doc:`recruiter-specific steps <recruiter_specific_deployment_steps>`
   for the correct value for your recruiter.

-  Double-check all settings mentioned in `recruiter-specific deployment
   steps <recruiter_specific_deployment_steps.html#recruiter-specific-deployment-steps>`__.

-  To deploy the experiment, run the following command from the
   experiment directory. Choose the server according to your deployment
   needs; see `Provisioning <provisioning.html#provisioning>`__.

   .. code:: bash

      psynet deploy ssh --app <app_name> --dns-host <your-subdomain>.<your-domain> --server <your-subdomain>.<your-domain>

-  Do not use an underscore character (``_``) in ``<app_name>``. It can
   cause an error during deployment.

**Example deployment:**

.. code:: bash

   psynet deploy ssh --app my-experiment --dns-host alice.<your-domain> --server alice.<your-domain>

**The app will be deployed to:**
``<app_name>.<your-subdomain>.<your-domain>``

**The logs will be available under:**
``logs.<your-subdomain>.<your-domain>``

**Note that the app name will be visible to participants, as it’s used
in the experiment URL. You can make it meaningful to you, but make sure
it does not give away too much to your participants.**

When the experiment is successfully deployed, the terminal prints the
dashboard URL and login credentials. It will look similar to this:

.. code:: text

   You can now log in to the console at
   https://admin:XXX@probe-tone.18.170.62.137.nip.io/dashboard
   (user = admin, password = XXX)

   ✔ Saving a snapshot of the code to
   /Users/kevin.nguyen/psynet-data/launch-data/probe-tone-experiment\__mode=live\__launch=2023-10-10--14-18-12/code…

Save this link to the dashboard so that you are able to
`monitor <monitoring_and_managing.html#monitoring-managing>`__ the dashboard during deployment.

Troubleshooting a prolonged launch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes the experiment appears to be stuck for more than a few minutes
at the "Launching experiment" stage. The best first step is to inspect
the Dozzle logs for HTTP server errors:
https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html#deploying-experiments-via-ssh

There is a known issue where ``nip.io`` refuses to provide an HTTPS
address because of quota constraints. Other common causes include an
invalid server name or incorrect Prolific parameters. If the terminal
does not show a clear error, the Dozzle logs often contain a more useful
message.

Redeployment from archive
-------------------------

If you need to redeploy from an archive, see:
https://psynetdev.gitlab.io/PsyNet/deploy/deploy_from_archive.html
