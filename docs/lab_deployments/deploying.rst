Deploying 
==========

🛑 Sanity check 
---------------

Version control
^^^^^^^^^^^^^^^

Before you deploy your experiment, you need to:

-  have a git repository, if you haven’t create one by typing git init

-  commit your changes, i.e. no staging or modified filesdefine a remote
      and push your commits to it

see `Prerequisites <#prerequisites-one-time-setup>`__

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

5. **Update Your requirements.txt**

Once you’ve confirmed the latest commit, update the version (or commit
hash) reference in your requirements.txt file if you are pointing to a
specific commit or branch. This ensures your virtual environment is
linked to the correct version of PsyNet.

6. **Install the Updated Requirements**

.. code:: bash

   pip install -r requirements.txt

This command installs any new dependencies and updates existing ones as
necessary.

7. **Generate Constraints**

   .. code:: bash

      psynet generate-constraints

Requirements file and dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure your local PsyNet (and Dallinger) version is the same as the
version listed in requirements.txt (otherwise you will get an error when
you try to deploy later).

Also, generate the constraints using ``psynet generate-constraints``.
Remember to run this command again if you make any changes to
requirements.txt.

Also try out your experiment via the Docker installation:

.. code:: bash

   docker/psynet debug local

before trying it out on the server, to check you did not forget to add 
any dependencies in the requirements.txt file.

Make sure your sufficiently tested your experiment, see
`Test <#test>`__.

Remote debug
^^^^^^^^^^^^

Before deployment, you need to make sure your experiment runs
successfully on a remote server. Make sure you did all types of
`tests <#test>`__ and thus did a remote debug.

🛑 Actual deployment 
--------------------

-  Set up your experiment for actual deployment, e.g., check you have
      the actual number of trials and/or networks (you may have changed
      this during hotair deployment).

-  Set your ‘recruiter’ config parameter to ‘prolific’ or ‘lucid’ again
      depending on which recruiter you are using.

-  Doublecheck all settings mentioned in `recruiter-specific deployment
   steps <#recruiter-specific-deployment-steps>`__.

-  To actually deploy your experiment, run the following code from your
      experiment folder (determine the server type according to your
      need; see `Provision <#provisioning>`__):


   .. code:: bash

      psynet deploy ssh --app <app_name> --dns-host <subdomain>.cap-experiments.com --server <subdomain>.cap-experiments.com

-  You must not use a "\_" character in the <app_name>. This would lead
      to an error during the deployment process.

**Example deployment to an EC2 server:**

.. code:: bash

   psynet deploy ssh --app probe-tone --dns-host elif.cap-experiments.com --server elif.cap-experiments.com

**Example deployment to an internal server at the Cornell University:**

.. code:: bash

   psynet deploy ssh --app <app_name> --server experiments1.cococo-lab.cornell.edu --dns-host experiments1.cococo-lab.cornell.edu

currently we are mainly using use the original cap-experiment,
cap-experiments3 and cap-experiments4 for the experiments. See `internal
servers <#internal-server>`__ for more info.

**The app will be deployed to:**
<app_name>.<subdomain>.\ `cap-experiments.com <http://cap-experiments.com/>`__

**The logs will be available under:**
logs.<subdomain>.\ `cap-experiments.com <http://cap-experiments.com/>`__

**Note that the app name will be visible to participants, as it’s used
in the experiment URL. You can make it meaningful to you, but make sure
it does not give away too much to your participants.**

| When the experiment is successfully deployed, you will see this
  message printed in the terminal with the information to access the
  dashboard!
| You can now log in to the console at
  https://admin:XXX@probe-tone.18.170.62.137.nip.io/dashboard (user =
  admin, password = XXX)

   ✔ Saving a snapshot of the code to
   /Users/kevin.nguyen/psynet-data/launch-data/probe-tone-experiment\__mode=live\__launch=2023-10-10--14-18-12/code…

Save this link to the dashboard so that you are able to
`monitor <#monitoring-managing>`__ the dashboard during deployment.

**Troubleshooting a prolonged Launching experiment**

Sometimes you would see the experiment get “stuck” for a prolonged
duration (more than a few minutes) on the “Launching experiment” stage.
A very good way to understand what is happening, is to have a look in
the dozzle logs (http server) for errors, as explained here:
​​\ https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html#deploying-experiments-via-ssh

There is a known issue with nips.io refusing to give a https address due
to quota constraints. In addition, there are a few other errors that may
occur, such as a server name or incorrect prolific parameters. In the
event that a direct error does not appear in the console, an informative
error message in the dozzle logs may assist in identifying the problem.

Redeployment from archive
-------------------------

If you want to redeploy from archive, you can check this page:
https://psynetdev.gitlab.io/PsyNet/deploy/deploy_from_archive.html
