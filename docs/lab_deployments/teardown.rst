Teardown
========

The teardown steps depend on the server type you used. Follow the
section that matches your setup.

EC2 Server
----------

If you provisioned an EC2 server, terminate it after you have finished
exporting your data. EC2 servers incur charges while running, so
terminating promptly avoids unnecessary costs:

.. code:: bash

   dallinger ec2 teardown --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

**You must export all data before teardown. Once the server is
terminated, any data that was not exported is permanently lost.**

If you need to delete the app without tearing down the server (for
example, when redeploying from archive on the same server), use:

.. code:: bash

   psynet destroy ssh --app <app_name> --server <your-subdomain>.<your-domain>

.. note::

   **Destroy the app** when you have exported the data and will need to
   reuse the same server, for example when redeploying from archive
   (e.g., when assets are stored on the server).

.. note::

   **Teardown the server directly** when you have exported all the data
   and will not need the server anymore.

.. warning::

   Every time you destroy an app you also need to stop the related
   Prolific experiment. Each redeploy creates a new Prolific experiment,
   and you can exclude participants from earlier deploys via the Prolific
   platform.

For multi-day deployments, you can **stop the EC2 instance overnight**
to reduce costs. You will still incur minimal charges for storage, but
the running charges stop. Do not forget to terminate the instance when
you are fully done. See the stop/start commands in
:doc:`Provisioning <provisioning>`.

Internal or Physical Server
----------------------------

If you used an internal or physical server, delete the app once your
experiment is done and you have exported all data:

.. code:: bash

   psynet destroy ssh --app <app_name> --server <your-server-hostname>
