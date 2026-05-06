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

Group skills
------------

How to investigate errors?
^^^^^^^^^^^^^^^^^^^^^^^^^^

When programming, it frequently happens that you can get stuck. It is
okay to ask colleagues for help, but you should avoid asking questions
that have been asked before.

If you encounter an error, carefully inspect the stack trace. You can
click on the links to the files to inspect the lines where things break.
Also, scroll up to see if the error here was actually caused by
something else. Quite often the last error is just the ‘symptom’ but the
real error is above.

To get more insight on the issue, put a break point at the position
where your code breaks. This usually gives you more information about
why the error occurs. See `Debugging section <prerequisites.html#debugging-in-pycharm>`__.

Once you identified where your problem is, try searching for the
substring of error messages on Slack and on Google. Usually the last
line of the trace is the error you want to look for.

For example in this stack trace the last line is most relevant:

.. code:: text

   INFO:root:Compiling translation file on demand
   /Users/jakobnieder/Documents/MPI-frank/colours/color-naming_proj/color-naming/locales/el/LC_MESSAGES/experiment.po.

   Traceback (most recent call last):
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/bin/psynet", line 8, in <module>
       sys.exit(psynet())
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 1157, in __call__
       return self.main(*args, **kwargs)
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 1078, in main
       rv = self.invoke(ctx)
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 1688, in invoke
       return _process_result(sub_ctx.command.invoke(sub_ctx))
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 1688, in invoke
       return _process_result(sub_ctx.command.invoke(sub_ctx))
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 1434, in invoke
       return ctx.invoke(self.callback, **ctx.params)
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/core.py", line 783, in invoke
       return __callback(*args, **kwargs)
     File "/opt/homebrew/Caskroom/miniforge/base/envs/psynet/lib/python3.10/site-packages/click/decorators.py", line 33, in new_func
       return f(get_current_context(), *args, **kwargs)
     File "/Users/jakobnieder/psynet/psynet/command_line.py", line 755, in deploy__docker_ssh
       _pre_launch(
     File "/Users/jakobnieder/psynet/psynet/command_line.py", line 639, in _pre_launch
       run_pre_checks(mode, local_, heroku, docker, app)
     File "/Users/jakobnieder/psynet/psynet/command_line.py", line 888, in run_pre_checks
       exp = get_experiment()
     File "/Users/jakobnieder/psynet/psynet/experiment.py", line 2509, in get_experiment
       return import_local_experiment()["class"](db.session)
     File "/Users/jakobnieder/psynet/psynet/experiment.py", line 361, in __init__
       config_initial_recruitment_size = self.get_initial_recruitment_size()
     File "/Users/jakobnieder/psynet/psynet/experiment.py", line 731, in get_initial_recruitment_size
       return get_and_load_config().get("initial_recruitment_size")
     File "/Users/jakobnieder/psynet/psynet/experiment.py", line 108, in get_and_load_config
       config.load()
     File "/Users/jakobnieder/Dallinger/dallinger/config.py", line 306, in load
       self.load_defaults()
     File "/Users/jakobnieder/Dallinger/dallinger/config.py", line 303, in load_defaults
       self.load_experiment_config_defaults()
     File "/Users/jakobnieder/Dallinger/dallinger/config.py", line 347, in load_experiment_config_defaults
       self.extend(exp_klass.config_defaults(), strict=True)
     File "/Users/jakobnieder/psynet/psynet/experiment.py", line 848, in config_defaults
       expected_type = config_types[key]
   KeyError: 'show_bonus'

Try searching for show_bonus and KeyError in Slack. While the first
query show_bonus is more specific, nobody encountered the specific error
with this config key. The next step would be to look for the more
generic error message KeyError in Slack. As you can see in the
screenshot, Pol already had the same issue but with a different key.

.. image:: /_static/images/lab_deployments/image37.png
   :width: 8.5in

The solution was to make sure you are on the correct psynet commit hash.
It’s best to start searching Slack. Searching Google is particularly
helpful if the error does not occur in Psynet or Dallinger but in
dependencies (e.g., numpy, or librosa) or 3rd party software (e.g.,
docker). Google usually points to helpful directions. You can also put
the error or parts of it in double quotes, which will give you exact
matches. Also note that all public issues for PsyNet and Dallinger are
public and thus searchable via Google. Some group members have also used
ChatGPT for debugging, which you can if Google or Slack don’t give you
the answer.

How to ask for help?
^^^^^^^^^^^^^^^^^^^^

Once you identified the cause of the problem, you can ask your
colleagues.

-  **Make sure you write in a public channel** i.e. #psynet-support if
   it concerns psynet, #online-experiments if it considers online
   experiments (including CAP, internal package), or #programming if
   it is a general question. *Do not send direct messages to people
   to ask for help.* Your replies and solutions cannot be found by
   other group members. Also, this will allow all group members to
   respond and not a handful of them. Clearly indicate if it is an
   error you are facing or if its more a general question or comment.

-  **Be thoughtful about each other’s time.** A core philosophy of the
   group is that it’s a waste of time to be stuck on something and
   that a small amount of time of other people can get you going.
   However, it’s a thin balance between wasting group members time
   and being stuck on a problem for too long. As a rule of thumb, if
   you are stuck on the same problem for more than an hour, you need
   help. But make sure you did all possible steps to look and find
   the cause of the problem, see `previous
   section <setting_up_the_experiments.html#how-to-investigate-errors>`__.

-  **Be detailed.** Make sure you have identified the location of your
   problem. Avoid making wild claims, e.g. say the error occurs in
   psynet but psynet does never occur in the stack trace. When you
   state your error message, you need to be very specific:

   -  *Give some context:* Describe what you want to do.

   -  *Location of the error:* Tell us which error occurs and where it
      occurs.

   -  *Commit hash:* Tell us which psynet and dallinger commit hash you
      are using locally and which ones you use in the
      requirements.txt

   -  *Docker or virtual environment:* Tell us if you are using docker
      or a virtual environment.

   -  *Stack trace:* Always paste the full stack trace to your problem

   -  *Minimal working example:* If you can provide a minimal working
      example, e.g. a psynet demo where it occurs or a link to a Git
      repository

-  **Post the final solution.** Once you found the solution to the
   problem post it in the thread in Slack so future users (or future
   you :wink:) will remind the solution.

