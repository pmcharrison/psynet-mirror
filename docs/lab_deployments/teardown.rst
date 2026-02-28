Teardown
========

This process depends on the server type so please read the part
according to the server you used.

Remote (EC2) Server 
--------------------

If you provisioned an EC2 server, once you are done with your
experiment, you have to teardown the server:

.. code:: bash

   cap ec2 teardown --name <server_name> --region <region> --dns-host <subdomain>.cap-experiments.com

for example:

.. code:: bash

   cap ec2 teardown --name tapping3 --region us-west-2 --dns-host nori.cap-experiments.com

**You should not forget to turn off your instance since it cost
us money every hour!**

In case you would like to delete the app without tearing down the
server, use:

.. code:: bash

   psynet destroy ssh --app <app_name> --server <server_name>

.. note::

   **Destroy the app** when you have surely exported the data and will
   later need to reuse the same server, for example when redeploying the
   experiment from archive on the same server (e.g., when you have assets on
   the server).

.. note::

   **Teardown the server directly** when you have surely exported all
   the data and will not need the server anymore.

.. warning::

   Every time you destroy an app you also need to stop the related Prolific 
   experiment. Every redeploy creates a new Prolific experiment (you can then 
   exclude participants that participated in the first deploy via the Prolific 
   platform).

.. _internal-server-1:

Internal Server
---------------

If you used an internal server at the institute, all you need to do is
to delete the app from the server once your experiment is done and you
exported all your data. Here is the command:

.. code:: bash

   psynet destroy ssh --app <app_name> --server <server_name>

.. _section-6:
