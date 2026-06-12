Provisioning
============

Servers
-------

PsyNet experiments are deployed to an SSH-accessible Linux server. You
can use several types of server depending on your setup:

- **Your own physical server**: install Ubuntu and expose it to the
  internet. See the :doc:`physical server setup guide
  <../deploy/physical_server_setup>`.
- **A cloud provider (e.g., AWS EC2, Hetzner, Contabo)**: rent a virtual
  machine with SSH access. See the :ref:`SSH server guide <ssh_server>`
  and :ref:`AWS server setup guide <aws_server_setup>`.
- **A lab-provided internal server**: if your lab has a shared server,
  follow your lab's instructions for adding it to Dallinger.

Once you have a server, register it with Dallinger once:

.. code:: bash

   dallinger docker-ssh servers add --host <your-server-hostname> --user <your-username>

For the full list of server options and trade-offs, see the
:doc:`web servers overview <../deploy/web_servers>`.

EC2 servers (AWS automatic provisioning)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PsyNet supports automatic provisioning of AWS EC2 servers, which is
convenient for cloud deployments. Before using the commands below, make
sure AWS credentials, SSH access, DNS, and the Docker registry are
configured as described in the :ref:`AWS server setup <aws_server_setup>`
and :ref:`SSH server <ssh_server>` guides.

EC2 servers operate on a pay-as-you-go model. You are charged while the
server is running, so it is important to monitor usage and tear the
server down when you are finished.

The EC2 workflow includes:

1. Choose the region closest to your participants.

2. Set up a server in this region. This is provisioning.

3. Deploy or debug to this server with PsyNet.

4. Monitor your experiment and export your data regularly.

5. Wait for the experiment to finish, or finish it manually.

6. Export once more and save your results.

7. Terminate the server. This is teardown.

Selecting the region
^^^^^^^^^^^^^^^^^^^^

First, decide which region to deploy to. To list the available regions,
run:

.. code:: bash

   dallinger ec2 list regions

For example, choose ``us-east-1`` for participants in the eastern United
States. In general, the server should be close to where your
participants are located.

List of all instances
^^^^^^^^^^^^^^^^^^^^^

Instances can have the following states: pending, running,
shutting-down, terminated, stopping, stopped. You can list all instances
with:

.. code:: bash

   dallinger ec2 list instances

To only list instances which are running, run:

.. code:: bash

   dallinger ec2 list instances --running

You can also filter by region:

.. code:: bash

   dallinger ec2 list instances --region <region>

Or filter to only running instances in a specific region:

.. code:: bash

   dallinger ec2 list instances --region <region> --running

Provision an EC2 server instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you choose an EC2 instance, provision the server. After provisioning,
you will be charged until you stop or terminate the instance.

Important: export your data before you tear down the server. *If you do
not export the data first, the data are lost and there is no way to
retrieve them.*

Before you teardown the instance make sure:

-  The experiment is stopped on the recruiter. For example, in Prolific
   the experiment should be stopped and no longer active.

-  You have exported the data and run ``export.py`` to check that the
   exported data are usable.

You can provision an EC2 instance on demand:

.. code:: bash

   dallinger ec2 provision --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain> --type <type>

Pick a server name that is easy to recognize. Start the name with your
own name or a short identifier so others can tell who deployed it. A
name like ``alice-melody-batch2`` is good; ``melody123`` is not. The
recommended convention is:

.. code:: text

   name-experiment-version

For example, to collect data from participants in the US:

.. code:: bash

   dallinger ec2 provision --name alice-melody-batch2 --region us-west-2 --dns-host alice.<your-domain> --type <type>

Specify a custom subdomain that reflects your identity so the server URL
is recognizable. The full experiment URL will combine the subdomain and
the app name, for example:
``alice-melody-batch2.alice.<your-domain>``.

Choose the instance type according to your needs. ``m7i.large`` is
recommended for debugging, and ``m7i.xlarge`` is recommended for live
deployment. For example:

.. code:: bash

   dallinger ec2 provision --name alice-melody-batch2 --region eu-west-3 --dns-host alice.<your-domain> --type m7i.xlarge

If you use ``LocalStorage`` instead of S3 storage and the experiment
creates large stimuli, such as iterative singing or GSP experiments,
make sure the instance has enough storage. *If the instance runs out of
storage during the experiment, the experiment may crash.* Alternatively,
use ``S3Storage`` for experiments with many assets. If the experiment
does not create new assets, the default storage is usually sufficient.
You can find instance storage information in the AWS EC2 documentation:
https://aws.amazon.com/ec2/instance-types/

Usually, PsyNet should be responsible for uploading assets to storage.
For more information, see the :doc:`Assets tutorial
<../tutorials/assets>`.

During the provisioning, all steps are printed to the terminal. At the
end, you should see something like this printed in the terminal:

.. code:: text

   Connecting to alice.<your-domain>

   Connected.

   DNS record set up!

   Host registered in dallinger

   Provisioning complete! Time taken: 192.402161359787. alice-step-en is
   ready at ec2-52-91-24-127.compute-1.amazonaws.com

You can use Dozzle to view experiment logs and monitor server
performance. To get the Dozzle URL, add ``logs.`` in front of the DNS
hostname. For example:

.. code:: bash

   logs.alice.<your-domain>

Stopping an EC2 server instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For multi-day deployments, you can **stop the EC2 instance overnight**
to reduce costs. While you won't be charged for running the server
during the stopped period, you will still incur minimal charges for
storage. Do not forget to terminate the server when the experiment is
done; see :doc:`teardown`.

To stop the instance:

.. code:: bash

   dallinger ec2 stop --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

The next day, **start the instance again**. This reboots all Docker
containers and experiments, so double-check that the experiment still
works after the restart. To start the instance:

.. code:: bash

   dallinger ec2 start --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

.. _lab-deployment-ssh-into-instance:

SSH into the instance
---------------------

To SSH into the EC2 server manually, use:

.. code:: bash

   ssh <SERVER_URL>

For example:

.. code:: bash

   ssh ec2-18-170-223-29.eu-west-2.compute.amazonaws.com

SSH access is useful if you need to restart a Docker container or inspect
assets on the server.

Advanced users: create custom instances
---------------------------------------

For certain use cases, such as setting up your own synthesis server, you
may want to programmatically configure a custom EC2 server. This is an
advanced workflow that depends on your lab's infrastructure and should
be documented in your lab's internal deployment documentation. Most
experiments should use the standard provisioning command described
above.
