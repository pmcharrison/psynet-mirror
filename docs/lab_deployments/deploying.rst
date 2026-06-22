Launch the experiment
=====================

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

Requirements and dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure the PsyNet and Dallinger versions you tested locally match the
versions listed in ``requirements.txt`` and ``constraints.txt``. If you
change ``requirements.txt``, regenerate and commit ``constraints.txt``:

.. code:: bash

   psynet generate-constraints

For the canonical dependency workflow, see
:doc:`Dependencies <../experiment_development/dependencies>`. Before
deploying, test the exact environment locally with ``psynet debug local``
and complete the testing checklist in
:doc:`general_deployment_process`.

Remote debug
^^^^^^^^^^^^

Before deployment, you need to make sure your experiment runs
successfully on a remote server. Make sure you did all types of
:ref:`tests <lab-deployment-test>` and thus did a remote debug.

.. _lab-deployment-actual-deployment:

Run the deployment command
--------------------------

-  Set up the experiment for live deployment. For example, restore the
   production number of trials or networks if you reduced them during
   hotair testing.

-  Set the ``recruiter`` config parameter to the intended live recruiter,
   for example ``prolific`` or ``lucid``. Note: PsyNet still uses the
   name ``lucid`` internally for CINT deployments; consult the
   :doc:`recruiter-specific steps <recruiter_specific_deployment_steps>`
   for the correct value for your recruiter.

-  Double-check all settings mentioned in
   :doc:`recruiter-specific steps <recruiter_specific_deployment_steps>`.

-  To deploy the experiment, run the following command from the
   experiment directory. Choose the server according to your deployment
   needs; see :doc:`Provisioning <provisioning>`.

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
   https://admin:XXX@<app_name>.<your-subdomain>.<your-domain>/dashboard
   (user = admin, password = XXX)

   ✔ Saving a snapshot of the code to
   /Users/<your-user>/psynet-data/launch-data/<app_name>\__mode=live\__launch=<timestamp>/code…

Save this link to the dashboard so that you are able to
:doc:`monitor <monitoring_and_managing>` the dashboard during deployment.

Troubleshooting a prolonged launch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes the experiment appears to be stuck for more than a few minutes
at the "Launching experiment" stage. The best first step is to inspect
the Dozzle logs for HTTP server errors. See
:ref:`SSH deployment <ssh_server>` for the canonical deployment and log
inspection workflow.

There is a known issue where ``nip.io`` refuses to provide an HTTPS
address because of quota constraints. Other common causes include an
invalid server name or incorrect Prolific parameters. If the terminal
does not show a clear error, the Dozzle logs often contain a more useful
message.

Redeployment from archive
-------------------------

If you need to redeploy from an archive, see
:doc:`Deploying from archive <../deploy/deploy_from_archive>`.
