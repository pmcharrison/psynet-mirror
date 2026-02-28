Provisioning
============

🛑 Servers 
----------

You can use two types of servers for deployment: **Internal servers**
and **EC2 servers**. Each has its own use case depending on where you're
deploying.

**Internal Server**
^^^^^^^^^^^^^^^^^^^

This server is located at the Cornell. Using this server helps reduce
costs, as deployments to them are free, unlike EC2 servers, which
results in a significant cost. This is particularly important Currently,
we have the following server available:

   · experiments1.cococo-lab.cornell.edu

In order to use an internal server, you need to add it locally. This
setup is required only once, after which you will have continuous access
to the server. Please follow the provided command to add the desired
internal server. You need to change the host according to which server
you want to use:

.. code:: bash

   dallinger docker-ssh servers add --host <internal_server_host> --user co3


For example:

.. code:: bash

   dallinger docker-ssh servers add --host me.cap-experiments.com --user co3


.. code:: bash

   dallinger docker-ssh servers add --host experiments1.cococo-lab.cornell.edu --user co3


**EC2 Servers**
^^^^^^^^^^^^^^^

There are several ways to set up your own remote server, and we are
currently renting a server through Amazon Web Services (AWS). These
servers are known as EC2 (Elastic Compute Cloud). EC2 servers are
virtual machines that provide scalable computing power for cloud
applications. You should use EC2 servers if you want to deploy
experiments **outside of Europe**, as they allow you to choose the
region where the server will be hosted based on where your participants
are located. EC2 servers operate on a pay-as-you-go model. There is a
cost for each day you use it. It is therefore important to follow the
utilization steps carefully.

The EC2 workflow includes:

1. Decide on a region you want to deploy to, i.e. put the server where
      your people are

2. Set up a server in this region (provisioning),

3. Deploy or debug to this server in PsyNet

4. Monitor your experiment and regularly export your data

5. Wait for the experiment to finish or finish it manually

6. Export once more and save your results

7. Terminate your server (teardown)

Selecting the region
^^^^^^^^^^^^^^^^^^^^

First, determine in which region you want to deploy. To get a list of
the available regions, run:

.. code:: bash

   dallinger ec2 list regions

For example, the US (us-east-1).

Your server should be close to where your participants are.

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

You can also filter instances created via cap by running:

.. code:: bash

   dallinger ec2 list instances --pem cap

Also you can search only in one region:

.. code:: bash

   dallinger ec2 list instances --region <region>

You can also combine them, e.g.

.. code:: bash

   dallinger ec2 list instances --pem cap --region <region> --running

Provision an EC2 server instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you choose an ec2 instance, you need to "rent" the server
(`Provisioning <#provisioning>`__). Once you do that -- the clock is
ticking and you will be charged hourly until you release it
(`Teardown <teardown.html#teardown>`__).

Important: don't forget to export your data before you tear down the
server. *If you don’t all data is lost and there is NO way to retrieve
them.*

Before you teardown the instance make sure:

-  The experiment is stopped on the recruiter, e.g. in Prolific the
      experiment should be STOPPED and thus not active

-  Also make sure you exported your data and run export.py to make sure
      your data is not faulty

-  You can now provision an EC2 instance on-demand:

.. code:: bash

   dallinger ec2 provision --name <server_name> --region <region> --dns-host <subdomain>.cap-experiments.com --type <type>

-  Pick an instance name which is easy to recognize. Please include in
      the begining of the server name clear identifier of your name (or
      a shortened version of your name) for easy recognition.
      For example elif-melody-batch2 is good but ‘melody123’ would be
      bad. We want to be able to identify from the server name who
      deployed it, so deploying without your name is forbidden in our
      group. If you deploy this way we may delete your server and your
      content will be lost.

-  The server name thus should look like name-experiment-version

.. code:: bash

   dallinger ec2 provision --name elif-melody-batch2 --region <region> --dns-host <subdomain>.cap-experiments.com --type <type>

-  For example, if you want to collect data in the US your command will
      include the region name for the US, like this:

.. code:: bash

   dallinger ec2 provision --name elif-melody-batch-2 --region us-west-2 --dns-host <subdomain>.cap-experiments.com --type <type>

-  You should specify a custom subdomain for easier and more intuitive
      server access using recognizable domain names instead of raw IP
      addresses. The subdomain should reflect your identity, such as
      your name or a shorter version. For example:

.. code:: bash

   dallinger ec2 provision --name elif-melody-batch2 --region eu-west-3 --dns-host elif.cap-experiments.com --type <type>

The resulting URL for the experiment will combine the subdomain and the
experiment name. In this case, it’s slightly confusing because the
string “elif” appears twice: once in the subdomain
(elif.cap-experiments.com) and again in the experiment name
(elif-melody-batch2). As a result, the full URL of the experiment would
be: elif-melody-batch2.elif.cap-experiments.com. While having “elif”
appear twice might seem redundant, this follows the established
convention we expect you to folllow it.

You should use a different instance type according to your need.
m7i.large is recommended for debugging and m7i.xlarge is for deploying.
For example:

.. code:: bash

   dallinger ec2 provision --name tapping_deployment_batch_2 --region eu-west-3 --dns-host elif.cap-experiments.com --type m7i.xlarge

If you use LocalStorage and not S3 storage and large stimuli are being
created (e.g., in iterative singing experiments or GSP experiments), you
need to make sure you have sufficient storage on the instance. *If your
instance run out of storage during the experiment, the experiment might
crash!* **We therefore recommend using enough storage.** Alternatively
you can use S3Storage for experiments with many assets. If you don’t
create new assets sticking to the default storage would be sufficient.
Information about the list of assets can be found in amazon web page
(e.g here: https://aws.amazon.com/ec2/instance-types/)

Note that typically you would want that PsyNet is responsible for
uploading assets to Storage. More information about this is provided
here: https://psynetdev.gitlab.io/PsyNet/tutorials/assets.html#assets

During the provisioning, all steps are printed to the terminal. At the
end, you should see something like this printed in the terminal:

.. code:: text

   Connecting to elif.cap-experiments.com

   Connected.

   DNS record set up!

   Host registered in dallinger

   Provisioning complete! Time taken: 192.402161359787. elif-step-en is
   ready at ec2-52-91-24-127.compute-1.amazonaws.com

You can access Dozzle, a tool that allows you to view the logs of your
experiment and monitor the server's performance. To get the dozzle url,
simply add logs in front of the dns hostname. For example:

.. code:: bash

   logs.elif.cap-experiments.com

Terminate an EC2 server instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you’re finished with your experiment, terminate the EC2 server to
avoid ongoing charges. EC2 servers incur costs as long as they are
running, so it’s important to terminate them after your experiment is
completed. Follow the termination command:

.. code:: bash

   dallinger ec2 teardown --name <server_name> --region <region> --dns-host <subdomain>.cap-experiments.com

Alternatively, for multi-day deployments, you can **stop the EC2
instance overnight** to reduce costs. While you won't be charged for
running the server during the stopped period, you will still incur
minimal charges for storage. So don’t forget to terminate it once your
experiment is done. Stop instance:

.. code:: bash

   dallinger ec2 stop --name <server_name> --region <region> --dns-host <subdomain>.cap-experiments.com

The next day, simply **start the instance again**. This will reboot all
Docker containers and experiments, so it’s important to double-check
that the experiment is still working properly after the restart. Start
instance:

.. code:: bash

   dallinger ec2 start --name <server_name> --region <region> --dns-host <subdomain>.cap-experiments.com

SSH into the instance
---------------------

To ssh to the EC2 server instance manually, use:

.. code:: bash

   ssh <SERVER_URL>

For example:

.. code:: bash

   ssh ec2-18-170-223-29.eu-west-2.compute.amazonaws.com

SSHing into the instance is useful if you need to restart the Docker
container or need to access assets.

🔹 Advance users: create a Custom instances
------------------------------------------------------------

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

Note, you need to be more familiar with programming to do it.

🛑 Group skills
--------------------

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

.. _section-2:
