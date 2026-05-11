Provisioning
============

Servers
-------

PsyNet experiments are deployed to an SSH-accessible Linux server. You
can use several types of server depending on your setup:

- **Your own physical server**: install Ubuntu and expose it to the
  internet. See the
  `physical server setup guide <https://psynetdev.gitlab.io/PsyNet/deploy/physical_server_setup.html>`__.
- **A cloud provider (e.g., AWS EC2, Hetzner, Contabo)**: rent a virtual
  machine with SSH access. See the
  `SSH server guide <https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html>`__ and
  `AWS server setup guide <https://psynetdev.gitlab.io/PsyNet/deploy/aws_server_setup.html>`__.
- **A lab-provided internal server**: if your lab has a shared server,
  follow your lab's instructions for adding it to Dallinger.

Once you have a server, register it with Dallinger once:

.. code:: bash

   dallinger docker-ssh servers add --host <your-server-hostname> --user <your-username>

For the full list of server options and trade-offs, see the
`web servers overview <https://psynetdev.gitlab.io/PsyNet/deploy/web_servers.html>`__.

EC2 servers (AWS automatic provisioning)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PsyNet supports automatic provisioning of AWS EC2 servers, which is
convenient for cloud deployments. EC2 servers are virtual machines that
provide scalable computing power, and let you choose the region closest
to your participants.

Before you can use automatic EC2 provisioning, you need:

- An AWS account (https://aws.amazon.com/).
- AWS credentials configured for Dallinger (AWS access key ID and secret
  access key, typically set via ``~/.aws/credentials`` or environment
  variables).
- A PEM key file for SSH access, with permissions set to ``600``.
- A domain name and DNS setup (e.g., via AWS Route 53) that points a
  wildcard subdomain at your server. See the
  `AWS server setup guide <https://psynetdev.gitlab.io/PsyNet/deploy/aws_server_setup.html>`__
  for detailed instructions on registering a domain and configuring
  Route 53.
- Your PEM key path and security group name configured in
  ``~/.dallingerconfig``:

  .. code:: ini

     [EC2]
     ec2_default_pem = /path/to/your/key
     ec2_default_security_group = <your-security-group>

- A Docker registry accessible by the server (see the
  `Docker registry setup <https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html#setting-up-your-docker-registry>`__).
- S3 storage configured if your experiment creates many assets (see
  :ref:`Storage <storage>` below).

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
For more information, see:
https://psynetdev.gitlab.io/PsyNet/tutorials/assets.html#assets

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

Terminate an EC2 server instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you are finished with your experiment, terminate the EC2 server to
avoid ongoing charges. EC2 servers incur costs while they are running, so
terminate them after the experiment is complete:

.. code:: bash

   dallinger ec2 teardown --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

Alternatively, for multi-day deployments, you can **stop the EC2
instance overnight** to reduce costs. While you won't be charged for
running the server during the stopped period, you will still incur
minimal charges for storage. Do not forget to terminate it once your
experiment is done. To stop the instance:

.. code:: bash

   dallinger ec2 stop --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

The next day, **start the instance again**. This reboots all Docker
containers and experiments, so double-check that the experiment still
works after the restart. To start the instance:

.. code:: bash

   dallinger ec2 start --name <server_name> --region <region> --dns-host <your-subdomain>.<your-domain>

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
advanced feature and is typically not necessary for most users. Below,
we provide an initial guide on how to implement this:

.. code:: python

   from cap.docker.ec2 import prepare_instance
   import argparse

   parser = argparse.ArgumentParser(description="Synthesize a stimulus")
   parser.add_argument("--name", type=str, help="Instance name", required=True)
   parser.add_argument("--region", type=str, help="Region name", default="eu-central-1")
   parser.add_argument("--type", type=str, help="Instance type", default="m5.2xlarge")
   parser.add_argument("--storage", type=int, help="Storage in GB", default=32)
   parser.add_argument("--key", type=str, help="Key name", default="cap")
   parser.add_argument(
       "--image",
       type=str,
       help="Image name",
       default="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20230516",
   )
   parser.add_argument("--security", type=str, help="Security group name", default="cap")

   args = parser.parse_args()

   def callback(host, user, ip_address, executor):
       # TODO implement what you want to do with the instance
       pass

   prepare_instance(
       instance_name=args.name,
       region_name=args.region,
       instance_type=args.type,
       storage_in_gb=args.storage,
       key_name=args.key,
       image_name=args.image,
       security_group_name=args.security,
       callback=callback,
   )

This advanced workflow requires more programming and infrastructure
experience than the standard provisioning command.
