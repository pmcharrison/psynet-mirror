Deploying and Running Online Experiments
=============================================

Getting Started
===============

Important Notice:
-----------------

This document provides a step-by-step guide for deploying experiments.
To ensure a smooth deployment process, **certain sections are mandatory
for all users**, while others are specific to the recruiter you choose
(Prolific, CINT, or Lab Recruiter).

How to Use This Document
^^^^^^^^^^^^^^^^^^^^^^^^

- 🛑 **Must do**: Sections that are essential for everyone. These include
  prerequisites, setting up servers, and general deployment steps.
  Skipping these may lead to errors.
- 🔹 **Optional**: Sections that depend on your chosen recruiter. You can
  skip parts that do not apply to your deployment method.

What You Should Read First
^^^^^^^^^^^^^^^^^^^^^^^^^^

-  All users must complete the **prerequisites** before proceeding.

-  We strongly recommend reading up to the
   `Recruiter-Specific Deployment Steps
   <#recruiter-specific-deployment-steps>`__ section to fully understand
   the deployment process.

-  After that, verify CINT settings such as incidence rate, or continue
   with the recruiter-specific section that applies to your experiment.

This guide follows the current recommended deployment mode, which
utilizes Docker with CAP-specific AWS provisioning, primarily using
Prolific as a recruiter. However, if you are deploying via CINT or CAP
Recruiter, you will find detailed instructions in their respective
sections.

Glossary
--------

.. image:: /_static/images/lab_deployments/image29.png
   :width: 8.5in

**PsyNet**
   The package we use to create online experiments. It builds upon
   Dallinger.

**Experiment hosting**
   The *server* that hosts your experiment. PsyNet supports
   **internal servers** and **EC2 servers**. The best choice depends on
   participant location.

**Docker**
   Container software used to run an experiment in a fixed environment
   to avoid unexpected behavior. It is recommended for local debugging
   and deployment (see `Best practices <#best-practices>`__).

**Recruiter**
   A *service* that invites and pays participants with optional
   demographic requirements. Examples include Prolific, CINT
   (previously Lucid), and Lab Recruiter.

**Remote debug (SSH)**
   Running ``psynet debug ssh`` against a server. This is not the same
   as deployment or hotair.

**Deployment**
   Running ``psynet deploy ssh`` and activating a recruiter.

**Hotair**
   A participant-view test mode that is visible only to you and not to
   real participants. Use this before live deployment, and share the
   hotair link with team members for feedback.

**Archive (redeploy from archive)**
   Continuing data collection with an existing experiment. The archived
   experiment database file is called an archive.

**Provisioning**
   Setting up a server (here, typically via EC2).

**Teardown**
   Quitting a server (here, typically via EC2).

**initial_recruitment_size**
   The variable in your ``Experiment`` class that controls how many
   participants are invited initially. Avoid inviting more participants
   than your deployment can handle.

**Increase experiment size**
   Recruit more participants manually once current participants finish.
   Repeat until your target sample size is reached.

**Auto-recruit**
   Maintains a constant number of active participants. In this mode,
   ``initial_recruitment_size`` effectively becomes the desired steady
   concurrent count.

Best practices
--------------

One powerful way to reduce error is to streamline and unify the whole
process of running online experiments. We therefore make the following
recommendations. You can deviate from it, **but you must be aware that
you might encounter more issues and cannot always be supported.**

-  We expect you to use a Mac.

-  You need to have `Docker <#docker-desktop>`__ and `PyCharm <#pycharm>`__ installed,
      if you have a student ID or a proof of teaching, we recommend setting up `Github
      Copilot <#setup-co-pilot>`__

-  You should use Docker for local development and remote deployment.

-  For now we mainly support deployment to Prolific, CINT and
      Lab Recruiter. Make sure your experiment complies with the
      requirements.

Deployment Checklist
--------------------

1. **Prerequisites**

   - Set up PsyNet and complete all required installations.
   - Ensure Docker Desktop is `installed and running <#docker-desktop>`__.
   - Log in to the `group Docker registry <#log-into-the-docker-registry>`__ via GitLab (one-time).

2. **Experiment Setup**

   - Verify all experiment parameters.
   - Confirm locale, recruiter, and PsyNet estimates (time and payment).
   - Verify recruiter-specific settings:

     - **Prolific**

       - Set base payment (``wage_per_hour``) to ``0`` during
         deployment.
       - Verify qualifications (e.g., audio, nationality, microphone).

     - **CINT**

       - Verify PsyNet settings (e.g., aggressive timeout).

   - Use an appropriate storage backend (S3 or LocalStorage, not
     DebugStorage).

3. **Provisioning (Server Setup)**

   - Choose the correct server type (internal or EC2).
   - If using EC2, provision in the region closest to participants.
   - Confirm the EC2 instance type and local storage are sufficient if
     you use LocalStorage.

4. **Deployment**

   - Test your experiment end-to-end (including edge cases) in Docker.
   - Open Docker Desktop before deployment and confirm it is running.
   - Ensure ``requirements.txt`` is correct and constraints are generated.
   - If using Prolific, ensure account balance is sufficient.
   - Deploy to your server and publish the experiment in Prolific/CINT.
     Double-check demographics and technical qualifications in the
     marketplace.

5. **Monitoring & Management**

   - Start with 5-10 participants, then gradually scale once data and
     completions look good.
   - Monitor the dashboard to track participant progress and identify errors early.
   - Check Dozzle logs and inspect the error database table.
   - Monitor participant messages/free-text feedback and debug as needed.
   - Check data quality regularly (e.g., with an export script).

6. **Export & Termination**

   - Export all collected data for analysis.
   - If using an internal server, delete the app.
   - If using EC2, teardown (terminate) the server to avoid unnecessary costs.
   - Deposit your export to FS Jacoby.

**Important:** Check the recruiter-specific sections for
additional setup and monitoring details.

Prerequisites (One-time Setup) 
==============================

This describe all the setup process that needs to run experiments in the
main thread of the group.

You need to do this setup only once.

Note: we eventually separate this document from the deployment document.

PsyNet Installation 
--------------------

| For detailed installation instructions on macOS, please refer to the
  official guide here:
| *https://psynetdev.gitlab.io/PsyNet/installation/index.html*

Required Software & Accounts 
-----------------------------

🛑 Docker desktop 
^^^^^^^^^^^^^^^^^

Install Docker (https://www.docker.com/products/docker-desktop)

🛑 Log into the Docker Registry 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Make sure you are logged into the Group Docker registry via Gitlab with
your Gitlab credentials by running the command:

.. code:: bash

   docker login registry.gitlab.com

Set up docker account

1. Download docker

2. Create an account in docker.io: https://www.docker.com/

Note that it is possible to use another Docker registry in general (for
example of another group, or a global repository with your personal
account), but this is not recommended within the group (see more
information https://psynetdev.gitlab.io/PsyNet/deploy/ssh_server.html)

🛑 Pycharm
~~~~~~~~~~~~~~~~~~~~

Install PyCharm
^^^^^^^^^^^^^^^

-  Apply for educational discount
      (https://www.jetbrains.com/shop/eform/students )

-  Download and install `PyCharm Pro <https://www.jetbrains.com/pycharm/>`__.

**Important**, you need Pycharm Pro to be able to use the debugger.

Choose your environment
^^^^^^^^^^^^^^^^^^^^^^^

1. Open the project.

2. Go to settings -> Python interpreter:

3. Select show all:

.. image:: /_static/images/lab_deployments/image42.png
   :width: 8.5in

4. Go to plus sign

5. Go to existing environments and select from the list the one that
relates to you

.. image:: /_static/images/lab_deployments/image40.png
   :width: 8.5in

6. Press OK

7. Optional: Sometimes you already added the virtual environment, in
this case you can select it from the list on the left. However you may
need to turn of the filter (|image1|) in order to see it:

.. image:: /_static/images/lab_deployments/image17.png
   :width: 8.5in

Pressing the filter icon (the one on the right from the pencil icon):

.. image:: /_static/images/lab_deployments/image26.png
   :width: 8.5in

to test open the terminal in the lower part of the pycharm window, and
go to the folder of an experiment (e.g **demos/timeline**) and type
**psynet debug local**.

.. image:: /_static/images/lab_deployments/image47.png
   :width: 8.5in

Custom keymaps
^^^^^^^^^^^^^^

To further customize the ability to select a code and execute it go to
setting in python and search for “​​execute selection in python Console”
select this option:

.. image:: /_static/images/lab_deployments/image15.png
   :width: 8.5in

Add a simple shortcut for example replace this by Command+Enter. Now you
can select a code and Command+Enter will execute it in the console.

Debugging in Pycharm
^^^^^^^^^^^^^^^^^^^^

1. In the top right go to here:

.. image:: /_static/images/lab_deployments/image43.png
   :width: 8.5in

2. Select edit configurations:

3. Select + and debug server

4. Set the name to “Debug” and port to “1234”. If you use docker
locally. For Docker set the name to “Docker Debug”, set the port to
“12345” and change “localhost” to “host.internal”.

5. Copy the pip install command:

.. image:: /_static/images/lab_deployments/image8.png
   :width: 8.5in

6. Run it in the virtual environment.

7. Start the debugger.

8. Copy this line from the console to set a breakpoint.

.. image:: /_static/images/lab_deployments/image12.png
   :width: 8.5in

9. Put the breakpoint in your code

10. Your code should now stop at the breakpoint. You can now select
lines code in your console and press Command+Enter to execute the
selection in the debugger. You can see the variables when looking into
“Debugger”.

.. image:: /_static/images/lab_deployments/image31.png
   :width: 8.5in

9. Perform the following changes to the pycharm debug settings: go to
preferences and search for python debugger unselect “attach to
subprocesses” and select “gevent compatible”

.. image:: /_static/images/lab_deployments/image24.png
   :width: 8.5in

Setup Co-Pilot
^^^^^^^^^^^^^^

Copilot gives you autocomplete-suggestions for programming

Website to CoPilot
(https://plugins.jetbrains.com/plugin/17718-github-copilot )

In Pycharm go to Preferences -> Plugins-> Marketplace and look for
CoPilot

.. image:: /_static/images/lab_deployments/image55.png
   :width: 8.5in

click on Install and restart PyCharm

now you should see CoPilot in “Installed”

🛑 Git: Version control & Best Practices 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Setup shh keygen for gitlab

To use gitlab, you'll need to activate an SSH key. Follow these steps to
do so:

1. Run the following in terminal to generate an ED25519 key. When it asks 
   for a location, press enter (sets default location in ~/.ssh). It'll 
   then ask for a passphrase.

   .. code:: bash

      ssh-keygen -t ed25519

2. Run the following to copy the SSH key to the clipboard:

   .. code:: bash

      pbcopy < ~/.ssh/id_ed25519.pub

3. In the SSH Keys section of your gitlab account settings (look at
      "Preferences" in the upper right), paste your key in the "Key" box
      and replace "Title" with whatever you want to call your machine.

.. image:: /_static/images/lab_deployments/image23.png
   :width: 8.5in

4. Press "Add key." You should now be able to push and pull from gitlab
      by entering your passphrase.

2. Connect to Lab resources

Please ask a member to add you to the Computational Audition Lab Group
through the group account computational.audition.

Please ask Frank to add your SSH key to the group access list.

3. How to use git

**main** branch (used to be master branch): most stable form of the code

**dev** branch: constitutes the next version of the software that we are
preparing to release

useful commands:

.. code:: bash

   git init                      # create git repository
   git clone <url>               # clones the repository at url
   git status                    # show working tree status
   git add <files>               # add files
   git commit -m "my message"    # record changes
   git push                      # update remote
   git checkout <branch>         # switch branches

We strongly recommend using the pycharm IDE for committing.

It is important to make sure you are logged in to git registry before
deploying:

.. code:: bash

   docker login registry.gitlab.com

4. how to create a repository in computational.audtition

1. create a subgroup for the experiment series and then, go on “create
      project”

2. then go on “create project from blank

3. then you should see something like this:

4. name your project, uncheck “Initialize with README” and create the
      project\ |image2|

4. Push your local repository to computational.audition

1. Go to your experiment and make it a git repository:

   .. code:: bash

      git init

2. Add the remote repository:

   .. code:: bash

      git remote add origin <your_empty_repository>

3. Verify the remote is set up correctly:

   .. code:: bash

      git remote -v

4. Check which files are tracked or changed:

   .. code:: bash

      git status

   |image3|

5. Add files:

   .. code:: bash

      git add <files>

6. Record the changes with a message:

   .. code:: bash

      git commit -m "your_message"

7. Push to the remote:

   .. code:: bash

      git push origin main

How to git commit in Pycharm
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

-  Instead of using git commit -m “<your message>”, you can also commit
      via Pycharm.

-  Go to “Commit” on the left side and chak the files you want to
      commit. Type in the message below and press “Commit” or “Commit
      and Push” if you want to push too.

.. image:: /_static/images/lab_deployments/image51.png
   :width: 8.5in

.. _section-1:

🛑 Set credentials and cap-safe 
-------------------------------

You will need .dallingerconfig and cap.pem in your home directory.

To get the cap.pem follow the following instructions.

1. Clone the group safe:


   .. code:: bash

      git clone https://gitlab.com/computational-audition-lab/cap-safe.git


2. Inside the repository there is a file called “cap_keys.zip”

.. image:: /_static/images/lab_deployments/image2.png
   :width: 8.5in

3. Enter the password (same as safe password)

4. Inside you can find .dallingerconfig and cap.pem

5. Move it to your home directory

6. Set the proper permissions on the pem file. Go to the command line 
   terminal and type:

   .. code:: bash

      chmod 600 ~/cap.pem

If using windows you may also need to do this:

.. code:: bash

   icacls C:\path\to\cap.pem /inheritance:r /grant:r "%USERNAME%:R"

7. Be sure that you are at the latest Dallinger version and add the
following lines to your .dallingerconfig file:

[EC2]

ec2_default_security_group = cap

ec2_default_pem = /Users/<your username>/cap

Please be sure to type the correct username. If you do not know your
username then you can verify it by typing in the console: whoami. You
can verify that this line /Users/<your username>/cap to output of the
following command: ls ~/cap.pem

General Deployment Process
==========================

Experiment lifecycle
--------------------

Experiments follow a relatively fixed lifecycle.

-  `Design <#design>`__: Each experiment starts with a question to
      answer and requires an appropriate experiment design to address
      this. After some discussions with group members you can start
      implementing your experiment. If you get stuck designing your
      experiment you can get help from the group on Slack in
      #online-experiments.

-  `Test <#test>`__: The next stage is to test this design automatically
      and on a small group of colleagues and friends.

-  `Provision <#provisioning>`__: You can use internal servers if
      deploying within Europe or you can provision a remote server (EC2)
      if deploying outside of Europe. This process of setting up a
      server is called “provisioning”.

-  `Deploy <#deploying>`__: Once we reach the stage of a solid
      experiment, we can deploy it. This means that a group of online
      participants take your online experiment. For the first experiment
      you start with a pilot.

-  `Monitor <#monitoring-managing>`__\ **:** During the data collection
      we must monitor the experiment, we make sure we collect clean
      data, and in case in error compensate participants.

-  `Export & Terminate <#_7zmqxabf4x1m>`__: Once the experiment is done,
      we export the data once more and make sure our preliminary
      analyses run through. Once this is the case you can terminate the
      experiment.

-  `Teardown <#_srjlldjeb78l>`__: If you use an EC2 server, you should
      not forget to turn off the server when we are done.

-  `Report & Deposit <#report-deposit>`__: Report the details about your
      experiments (cost, duration, number of participants, etc.) and
      deposit your collected. **This is currently under construction the
      procedure for this would be reevaluated in the future.**

.. image:: /_static/images/lab_deployments/image7.png
   :width: 8.5in

Design
------

Designing an experiment is an iterative process. It often requires
multiple designs to get things right. Generally the design phase
together with the test phase should be what you spend most time and
energy on. Unlike lab experiments, once you get your experiment right,
it’s trivial to collect the data on participants.

We recommend the following procedure:

-  Think about the question you want to address, design an experiment
      that addresses this question

-  Get feedback on it from collaborators, group members and Nori

-  Once you settle on an idea, think about a psynet demo which
      implements parts of those ideas. Potentially you also need
      ‘building blocks’ from multiple demos. In some cases, you might
      even need to add custom functionality to psynet.

-  A central philosophy of the group is to unstuck each other. This
      means if you encounter a technical or design problem and thought
      about it yourself enough (say up to multiple hours), you should
      ask for help. The group provides two ways to get help:

   -  Via Slack, post your technical problem in #psynet-support or your
         design issue in #online-experiments. Your group members will
         reply.

   -  Raise it during standing

Test
----

Testing workflows

🛑 Testing on yourself 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It’s important to run the full experiment on yourself, as if you were a
real participant. This will give you a sense of how difficult the task
is, what the appropriate ``time_estimate`` of your task is, etc. Try to
catch edge cases, e.g. when you summarize nodes. One way to achieve this
is by running a smaller number of networks.

The easiest way to test on yourself is to debug on your local server by
running:

.. code:: bash

   docker/psynet debug local

from your experiment folder.

⚠︎ Make sure you are logged into the Group Docker registry via Gitlab
with your Gitlab credentials by running the command:

.. code:: bash

   docker login registry.gitlab.com

🔹 Testing with bots 
^^^^^^^^^^^^^^^^^^^^

Currently, testing with bots allows you to either run bots one at a
time (in serial) or to run several bots concurrently (in parallel). By
default, one bot will be run through your experiment. If you for
example want to test three bots in parallel, you can run:

.. code:: bash

   psynet test --n-bots 3 --parallel

It is now also possible to run bot tests on a remote server. This can be
useful to get a better idea of how the server will cope with large
numbers of participants. First you need to launch a debug experiment to
the server:

.. code:: bash

   psynet debug ssh --app my-experiment

Then you invoke psynet test, similar to before but with ssh instead of
local:

.. code:: bash

   psynet ssh --app my-experiment test --n-bots 3 --parallel

For more documentation on how to currently test with bots, see
`PsyNetDev
tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/tests.html>`__.

Things to look out for:

-  Does my experiment stop automatically?

-  Does it slow down?

   -  Possible causes and solutions include:

      -  Insufficient hardware: Reassess how much hardware you
            need and take 1.5x

      -  Inefficient code: Avoid large list comprehension (e.g.
            on all trials), check that custom synthesis code does not
            contain unneeded parts or slow code (for example creating
            high resolution visualization)

-  How many parallel participants can I serve?

-  Does my experiment use synthesis or resource-intensive
      analysis (e.g. analyzing syllables in recordings)?

🛑 Testing within the group 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   | Let other group members take your experiment and check if it’s
     working properly. **This is an obligatory step**. It will make sure
     your experiment runs remotely and it will give you qualitative
     feedback on your experiment.
   | Once you think your experiment is ready for remote
     debugging/testing:

-  Set up your experiment code for testing. Often, this means making a
      short version of the experiment with fewer trials and/or networks.

-  Set your ‘recruiter’ config parameter to ‘hotair’

-  Remote debug your experiment by `provisioning a
   server <#provisioning>`__, then running in the terminal from your
   experiment folder (determine the server type according to your
   need; see `Servers <#servers>`__):

   .. code:: bash

      psynet debug ssh --app <app_name> --dns-host <subdomain>.cap-experiments.com --server <subdomain>.cap-experiments.com

   Example:

   .. code:: bash

      psynet debug ssh --app probe-tone --dns-host elif.cap-experiments.com --server elif.cap-experiments.com

   This command will produce a **single recruitment link, make sure to
   save this link.**

-  Before sharing the link with the lab, try the experiment yourself
      again to check no new issues occur now that you are running on the
      server instead of locally. Run the remote experiment yourself and
      check whether it is working as expected (e.g., can you get to the
      end without errors, is the data saved, … ?). If you need to make
      changes to your experiment, make them on your computer and then
      rerun the previous command from your experiment folder. The remote
      app will then be stopped and re-created.

-  To share your remote debug app with pilot participants from the lab,
      use the **‘single recruitment link’** that is printed in the
      terminal once the app is launched on the server.

-  In #online_experiments on Slack, post a message including the single
      recruitment link. It’s also nice to list specific aspects of the
      experiment you would like feedback on.

-  Once you have data from the group, use that to write analysis code
      for your experiment. Check that your data were processed correctly
      (e.g., in GSP, does the synthesis work properly? In recordings,
      are recordings processed correctly?)

-  You can use this code later to `check the initial batch of
   data <#sanity-checks>`__ you gather when you deploy the experiment.

Since the group is not extremely large you might not encounter:

-  issues that occur when many people take the experiment
      simultaneously, or

-  issues that occur late in the experiment (e.g. after the first node
      is ready and a new one is created or slowness in the experiment
      caused by list comprehension on very large list that grow over the
      course of the experiment, such as all trials in an experiment)

..

   → Therefore, also you can run `Testing with
   bots <#testing-with-bots>`__

🔹 Automatic Translation 
------------------------

With PsyNet, it's easy to conduct experiments in different languages.
You can automatically translate your experiment into different languages
in no time.

The first step is to add this to your .dallingerconfig:

[Google Translate]

google_translate_json_path = ~/psynet-gtrans.json

[OpenAI]

openai_api_key = <see cap-safe>

Also, put the psynet-gtrans.json (find it in cap-safe) into your home
directory (~).

Ensure your psynet version is beyond commit hash
02a1cdded737d9fae294b789f7d5a5c288d59580 ("Autotranslation"). This is
the case for the latest master or the next Psynet release.

Usage

Translating your experiment is simple.

1. Set the locale of your experiment, e.g.:

.. code:: python

   class Exp(psynet.experiment.Experiment):
       config = {
           'locale': 'tr',  # iso-2 code for Turkish
       }

or add the following line to your config.txt

.. code::text

   locale = tr

2. Mark translations in your experiment.py

.. code:: python

   from psynet.utils import get_translator

   _ = get_translator()

   page = InfoPage(
       _("This text will be translated to the locale you set in the experiment")
   )

3. Now translate using psynet translate

Read the `whole
tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/internationalization.html>`__
for more information.

🛑 Recruiters
--------------------

We currently use three recruiters: **Prolific, CINT, and Lab Recruiter
(LR).** Please decide which one to use.

-  `Prolific <https://www.prolific.com/>`__ offers a high-quality,
      diverse participant pool, ideal for academic and market research.

-  `CINT <https://www.cint.com/>`__ provides access to a larger
      participant pool, making it particularly useful for recruiting
      participants across different countries and languages, allowing
      for more culturally diverse studies. The provisioning steps for
      both platforms are identical. For detailed instructions, please
      refer to the deployment steps for Prolific and CINT. Note that
      Lucid was recently acquired by CINT, a large global recruiter.

-  `Lab Recruiter <https://recruiter.cococo-lab.cornell.edu/>`__ (LR) is an
      internally established recruitment system that offers full control
      over participant selection without third-party involvement.
      Initially designed for recruiting musicians, it is now expanding
      to accommodate a broader range of participants tailored to the
      specific needs of experiments.

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

   dallinger docker-ssh servers add --host <internal_server_host> --user cap


For example:

.. code:: bash

   dallinger docker-ssh servers add --host me.cap-experiments.com --user cap


.. code:: bash

   dallinger docker-ssh servers add --host experiments1.cococo-lab.cornell.edu --user cap


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
(`Teardown <#teardown>`__).

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
why the error occurs. See `Debugging section <#debugging-in-pycharm>`__.

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
      section <#how-to-investigate-errors>`__.

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

Setting Up the Experiments 
==========================

Before deploying your experiment, you need to complete basic setup steps
that apply to all deployments. Most details, including specific
recruiter instructions, are covered in their respective sections—so this
section provides only the essential steps.

1) Define Experiment Configuration

   a. Ensure **all required parameters** are set (consent, title,
         description, payment, completetion time, participant size).

   b. run psynet estimate in the terminal to get estimated completion
         time and compensation.

   c. Use **appropriate storage (S3 or LocalStorage)** instead of
         DebugStorage.

2) Choose a Recruiter

   a. **Prolific, CINT, or Lab Recruiter**—each has different setup
         steps (see their
         `sections <#recruiter-specific-deployment-steps>`__).

   b. Configure the recruiter-specific settings after reading
      `Recruiter-Specific Deployment Steps
      <#recruiter-specific-deployment-steps>`__.

3) Test Your Experiment

   a. **Local test:** Run it on your machine first.

   b. **Hotair:** Use a private testing link before public deployment.

4) Final Check Before Deployment

   a. Verify that all steps recommended in your chosen recruiter’s
         section are followed.

   b. Discuss the payment strategy. Ensure you have enough balance on
         Prolific before launching.

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

Massive Deployments 
====================

(Deploying Multiple Experiments in Parallel)

- This specific implementation, designed by Pol, is currently available
  only in the development version of the framework: **psynet==13.0.0rc1**.

- Pin this version in your project's requirements.txt file and generate
  constraints for dependency management.

**Monitoring Real-Time Experiment Data: The basic_data Endpoint**
-----------------------------------------------------------------

Overview and Utility: Why Use **get_basic_data**?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The basic_data endpoint is a powerful feature designed to provide
**real-time access** to your experiment's data during deployment,
eliminating the need for constant manual data exports.

The core utility lies in the **get_basic_data** method you implement
within your experiment class. When deployed, this method exposes the
data through a dedicated, easily accessible **URL** (e.g.,
http://127.0.0.1:5000/basic_data?...).

**Key Benefits:**

-  **Real-Time Data Access:** You can access the most up-to-date
      experiment data without interrupting the deployment or running a
      separate export process.

-  **Easy Data Loading:** The URL allows you to load the experiment data
      directly into your analysis environment (like **Pandas** in Python
      or a **dataframe** in R) using standard library functions
      (pd.read_json, jsonlite::fromJSON).

-  **Monitoring:** This is especially useful when dealing with
      **multiple batches**. By leveraging **GET parameters** in the URL,
      you can easily switch between different views or batches of data
      (e.g., checking data for Batch A vs. Batch B) using the same
      framework.

-  **Custom Sanity Checks:** The accessible URL enables you to write
      your own automated scripts to continuously load the data and
      perform **sanity checks** (e.g., monitoring data quality, checking
      response distributions, looking for suspicious activity, or
      confirming the experiment is progressing as expected).

Implementation of the Experiment Method (**get_basic_data**)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use the /basic_data endpoint in your experiment, you need to
implement the get_basic_data method in your experiment class. The method
should return a list of dictionaries with the data you want to expose.
You can make this method as complex as you need. For example, you can
add GET parameters to the endpoint, e.g. /basic_data?sheet=participant
which allows to switch between different data sheets.

.. code:: python

   class Exp(psynet.experiment.Experiment):
       ...

       @classmethod
       def get_basic_data(cls, context=None, **kwargs):
           data = {
               "trial": [
                   # List all trials with their answers
                   {"id": trial.id, "answer": str(trial.answer)}
                   for trial in Trial.query.filter_by(failed=False, finalized=True).all()
               ],
               "participant": [
                   # List all participants with their last answer
                   {"id": participant.id, "answer": str(participant.answer)}
                   for participant in Participant.query.filter_by().all()
               ],
           }

           sheet = kwargs.get("sheet", "participant")
           if sheet not in data:
               raise DataError("Invalid sheet parameter")

           return data[sheet]

-  The data defined in your get_basic_data method is accessible
      in two ways: **via the Deployment Dashboard** and **directly via
      the Data URL**. When your experiment is running, you can easily
      view the structure and content of the exposed data by navigating
      to the **"Basic data"** tab on the dashboard. This page provides a
      Data URL and a Data preview pane, letting you instantly inspect
      the returned data and test different parameters. For automated
      monitoring, you can use the Data URL directly in analysis scripts
      (like pd.read_json(url)) to load the live data into a dataframe
      and run your custom sanity checks.

-  R Example:

..

   library(jsonlite)

   url <-
   "http://127.0.0.1:5000/basic_data?dashboard_user=cap&dashboard_password=capcapcap2021!"

   df <- fromJSON(url)

-  Python Example:

   .. code:: python

      import pandas as pd

      url = "http://127.0.0.1:5000/basic_data?dashboard_user=cap&dashboard_password=capcapcap2021!"
      df = pd.read_json(url)

.. image:: /_static/images/lab_deployments/image25.png
   :width: 8.5in

.. _section-3:

.. _section-4:

**Monitoring All Experiments at Once: Deployment Monitor**
----------------------------------------------------------

The deployment monitor provides a single, unified dashboard to
view and manage all your running and past experiment deployments. This
feature is crucial when running simultaneous experiments, as it
transforms complicated individual monitoring into a simple, automated
process.

**How to Use the Interface**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This monitor allows you to quickly assess the progress and
performance of every deployment at a glance:

1. **At-a-Glance Statistics:** For every deployment, you
      immediately see essential statistics, including:

   -  **Recruitment Status:** Whether the experiment is actively
         recruiting.

   -  **Runtime & Duration:** How long the experiment has been
         running and its estimated completion time.

   -  **Cost & Compensation:** The financial metrics associated
         with participant recruitment.

   -  **Participants & Errors:** The number of participants
         recruited and any recorded server errors.

2. **Filtering Deployments:** You can easily manage the
      complexity of multiple deployments using the filter menus at the
      top of the page. This allows you to quickly isolate groups of
      experiments based on recruiter, recruitment status, label and
      network status.

3. **Quick Shortcuts:** The shortcuts column on the right
      provides quick access to critical deployment tools. Here are some
      actions you can take:

   -  **URLs to data endpoint, dashboard, server (e.g., Dozzle),
      etc.:** Direct links to monitor server logs and performance,
      and more.

   -  **Export:** A shortcut to download the latest data for that
         specific deployment.

   -  **Notes:** An easy way to add, edit, or view important
         contextual notes about that deployment.

In short, the deployment monitor centralizes all deployment
information, making it simple to check the entire pipeline's status,
troubleshoot issues, and access data without navigating away from one
page. You can access it through the dashboard in the ‘Deployments’ tab.

.. image:: /_static/images/lab_deployments/image44.png
   :width: 8.5in

**Slack Integration: Real-Time Deployment Alerts** 
---------------------------------------------------

Integrate with Slack to get **instant, real-time alerts** for
your deployments. This is highly useful when you have multiple
simultaneous deployments. The PsyNet Bot automatically sends crucial
updates to the deployments channel.

**Configuration Steps**
^^^^^^^^^^^^^^^^^^^^^^^

1. **Join the Channel:** The PsyNet Bot reports to the central
      channel. Ask Elif to add you to the #deployments channel to
      receive notifications.

2. **Update the config in experiment.py**: Add the “notifier”:
      “slack” setting to your ‘config’,

..

   config = {

   "notifier": "slack",}

3. **Update ~/.dallingerconfig:** Add the following to your
      ``.dallingerconfig`` file:

..

   [Slack]

   slack_channel_name = deployments

   slack_bot_token = <see cap safe>

   experimenter_name = <your name>

   Note: Make sure your ``experimenter_name`` matches your name on
   Slack.

**Usage**
^^^^^^^^^

+---------+------------------------------------------------------------+
| Event   | Benefit & Actions                                          |
| R       |                                                            |
| eported |                                                            |
| by      |                                                            |
| PsyNet  |                                                            |
+=========+============================================================+
| Exp     | Instant Visibility: You're notified immediately when an    |
| eriment | experiment launches (including ID and URL). The alert      |
| started | includes the experiment dashboard link and login           |
| (and    | credentials for quick access.                              |
| cred    |                                                            |
| entials |                                                            |
| for     |                                                            |
| das     |                                                            |
| hboard) |                                                            |
+---------+------------------------------------------------------------+
| Recr    | Critical Alerts: Messages are sent for changes in the      |
| uitment | experiment's recruitment status (e.g., transition from     |
| updates | Recruiting to Taken down or Complete).                     |
+---------+------------------------------------------------------------+
| Error   | Critical Alerts: Receive immediate messages for errors.    |
| o       |                                                            |
| ccurred |                                                            |
+---------+------------------------------------------------------------+
| Exp     | Quick Access & Actions: The final completion status is     |
| eriment | noted. Every thread allows for quick actions, such as      |
| f       | manually exporting data, directly from the Slack thread.   |
| inished |                                                            |
+---------+------------------------------------------------------------+

By default such notifications will only occur when an experiment
is deployed (i.e. \\``psynet deploy\\`), not when it is run
locally in debug mode (i.e. \``\`psynet debug\\`). However, to
trial the Slack notification service locally, you can run \``\`psynet
deploy local\`.`

**Batch Automation for Massive Deployments**
============================================

When running multiple experiment variants across different
servers, locales, or conditions, manually repeating the provisioning,
deployment, and destruction steps is highly time-consuming and prone to
errors. The following scripts provide a framework to automate and
parallelize these processes, making massive deployments manageable.

Example Python scripts:

-  **Provisioning:** The batch_provision.py script automatically
      creates multiple EC2 instances (servers) across different AWS
      regions in parallel.

-  **Deployment:** The batch_deploy.py script iterates through a
      list of configurations, dynamically generating a unique config.py
      for each variant before deploying it to a specific server. This
      ensures every experiment is launched with consistent, correct
      parameters.

-  **Destroying:** The batch_destroy.py script allows for the
      quick and safe termination of multiple deployed applications
      across a host.

**Important: Adaptation is Required!**

These files are **only examples** and are designed to be adapted
to your specific experiment. You must edit the core configuration
variables found within each Python file before running them. Please
check each file for details.

These example scripts can be found and downloaded from the repo
cococo-shared-files <https://gitlab.com/cococo-shared/cococo-shared-files/-/tree/master/deployment/massive_deployment?ref_type=heads>`__.`

Monitoring & Managing 
======================

Once your experiment is deployed, continuous monitoring is essential to
ensure smooth data collection, handle participant issues, and optimize
recruitment. If you cannot do it yourself (e.g., due to time-zone
issues), you can contact Nori or Elif for help.

This section provides general guidelines, while recruiter-specific
details (Prolific, CINT, Lab Recruiter) can be found in their respective
sections.

🛑 Using the Dashboard 
----------------------

The experiment dashboard is your main tool for tracking and managing the
study. It is the same for each recruiter. It is printed on the terminal
after the deployment command (how to find the `dashboard
link <#actual-deployment>`__).

Key Features:

-  **Monitoring Tab:** View networks, nodes, parameters, and participant
      answers. Click shapes for details.

-  **Timeline Tab:** Track participant counts, completions, and
      failures. Also, see all the modules in your experiment and
      completion percentages.

-  **Database Tab:** View or export data via the Export Tab.

🛑 Monitoring Participants & Data Collection 
--------------------------------------------

-  Track participant progress (dropouts or errors).

-  Use **Dozzle logs** for real-time debugging. Regularly check for
      error messages in logs and fix critical issues immediately. (how
      to find the `dozzle link <#provisioning>`__)

-  Monitor Prolific/CINT marketplaces for recruiter-specific insights.

🛑 Participant Issues 
---------------------

Participants might directly contact you in some cases of errors and
issues.

Where Participants May Contact You:

-  **Prolific:** Via the Prolific messaging system.

-  **CINT:** currently not possible.

-  **Lab Recruiter:** Emails sent to coco-experiments@cornell.edu.

Messages in gmail account 
^^^^^^^^^^^^^^^^^^^^^^^^^^

It might also be the case that participants will text you on the group’s
gmail account computational.audition@gmail.com (you can find the
credential in cap-safe). It could be that your login has to be verified
through some further authentication. In that case, contact Nori for
help. This was an important mode of communication in the past but rarely
happens now.

When you are done with a message, move the message to the “Done”
subfolder. Sometimes, you will see emails, which contain bills and are
not related to your experiment. These mails should be moved to the
“accounts” subfolder.

🛑 Recruitment and Payment Strategies 
-------------------------------------

-  Start with a small recruitment batch (5-10 participants) and review
      data quality before increasing participation. After all these
      initial participants have finished the experiment, you should
      check that you do not get any errors and that your initial time
      estimate for the experiment is accurate.

-  Regularly increase recruitment size manually instead of relying on
      auto-recruit for the entire study.

-  Adjust wage per hour and completion time estimates based on actual
      participant behavior.

-  If you are using auto-recruit, stop it before reaching the final
      stages to prevent excess costs.

Exporting & Terminating
=======================

🛑 Export data
--------------------

You can export the data using following command:

.. code:: bash

   psynet export ssh --app <APP_NAME> --server <SERVER> --path <PATH_TO_STORE_YOUR_DATA>

For example:

.. code:: bash

   psynet export ssh --app color-exp --server elif.cap-experiments.com --path /Users/elif.celen/Experiments/color

🔹 Export script 
----------------

In the group we like to have a file called export.py which contains:

-  Sanity checks

-  Export of demographic information

-  Export of the raw results to some preprocessed format, and

-  Preliminary plots of the main results

🛑 Sanity checks 
^^^^^^^^^^^^^^^^

These checks are very important because it allows us to determine
problems from early on and in case of error allows to abort the
experiment without receiving many complaints and paying many
participants.

Checks you must implement are:

-  Are time estimates set properly? -> e.g. make a histogram over the
      time it took to do trials

-  Do people progress fully through the experiment?

-  Do people do the required number of people do your trials? If people
      should do 60 trials, you should get 60 trials per participants

Try to use assertions for those sanity checks.

Export demographic information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Read the required demographic information from the data, e.g. age and
gender from Participant.

Export of the raw results
^^^^^^^^^^^^^^^^^^^^^^^^^

Export your data to an output format you can use for plotting. E.g. save
a CSV you can import in Matlab or R.

Preliminary plot
^^^^^^^^^^^^^^^^

Make some preliminary plots to make sure you see the trend in the data.
If the results are very unexpected try to identify what can cause the
effect.

.. _best-practices-1:

Best practices
^^^^^^^^^^^^^^

Export regularly and run your export.py script. This way you can detect
problems from early on.

🛑 Export once more
-------------------

After you made sure that the experiment is completed export the data one
last time.

In a new version of PsyNet, your logs will be downloaded automatically
upon exporting. You will also see an automatic analysis of the log file.

.. _section-5:

🔹 Additional manual export in case of large assets
----------------------------------------------------------------------

| In case you are experiencing trouble exporting large assets using
  psynet export, you can also try to zip and export the assets manually
  from the ssh server. Take note that the assets will not have the same
  nice cleaned names as when exported via psynet export ssh!
| To do this manual export of the assets:

-  ssh to the server as explained in `SSH into the
   instance <#ssh-into-the-instance>`__

-  then you create a tar.gz of the assets folder on the server, by
      running in the terminal:

.. code:: bash

   tar -czvf $HOME/namefile.tar.gz $HOME/psynet-data/assets

-  leave the server, and on your local pc download this tar.gz by
      running in the terminal:

.. code:: bash

   scp -p 22 ubuntu@<SERVER_URL>:/home/ubuntu/namefile.tar.gz ~/Downloads

   to download the tar.gz file to your local Downloads folder (replace
   <SERVER_URL> by your servers URL)

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

   .. code:: bash

   psynet destroy ssh --app <app_name> --server <server_name>

.. note::

   **Destroy the app** when you have surely exported the data and will later 
   need to reuse the same server, for example when redeploying the experiment 
   from archive on the same server (e.g., when you have assets on the server).

.. note::

   **Teardown the server directly** when you have surely exported all the data 
   and will not need the server anymore.

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

Recruiter-Specific Deployment Steps
===================================

Prolific 🔹 
-----------

Setting up the experiment
~~~~~~~~~~~~~~~~~~~~~~~~~

Experiment costs
^^^^^^^^^^^^^^^^

1. To calculate the base payment for your experiment, set the
“\ **wage_per_hour**\ ” parameter in the config to 9 Pounds (Prolific
recommendation).

"wage_per_hour": 9

2. Run psynet estimate in the terminal and note your estimated
experiment duration and cost. You should include the cost and the
duration in your experiment’s title Also, say people need Chrome and
optionally headphones and microphones if needed.

3. In the get_prolific_settings() <#experiment-script>`__
function, specify the duration using the
"prolific_estimated_completion_minutes" parameter and the cost using the
"base_payment" parameter.

 

- For example, when you run psynet estimate, you will get a result like
  this one:

❯❯ Estimated maximum reward for participant: EUR4.95.

❯❯ Estimated time to complete experiment: 33 min.

- In this case, the prolific parameters must be as follows:

"base_payment": 4.95

"prolific_estimated_completion_minutes": 33,

4. After calculating the base payment, you **MUST** set the
**“wage_per_hour”** parameter to 0 for the actual Prolific deployment.
Otherwise, it would cause problems in the payment.

"wage_per_hour": 0

5. Make sure all time_estimates are set appropriately such that
the overall duration of your experiment (you get it from psynet
estimate) matches your expectation.

6. Check that the experiment costs are right:

-  Use your own data (and possibly but not mandatory the group
   data) to estimate how long it takes for each trial, pre-screeners,
   and the entire experiment

-  Start running (if possible) a small number of participants
   (e.g., 10) and try to see if your time estimate is wrong by more than
   30% - redeploy.

-  If you had run the experiment, update the run time based on
   real data.




Example of adapting the consent form to say 9 pounds per hour
while wage_per_hour in config is set to 0:
\*
customconsent.py <https://gitlab.com/computational-audition-lab/octa_projects-elinevg/octa_gibbs1/-/blob/main/customconsent.py?ref_type=heads>`__`

\*
templates/custom_main_consent.html <https://gitlab.com/computational-audition-lab/octa_projects-elinevg/octa_gibbs1/-/blob/main/templates/custom_main_consent.html?ref_type=heads>`__`

Payment strategy
^^^^^^^^^^^^^^^^

Nori- write this down.

-  Experiments with minimal pre-screening (e.g static experiments)

-  Experiments that needs some pre-screening (e.g GSP and chain
   experiments) 25% Traffic -> this is a classical use case to
   explicitly test; if you get 10 people, ~7-8 people should pass

-  Experiments with “technical” pre-screening.

-  Experiments with high percentage of filtered people (more 25% and
   particularly more than 50%). → separate experiment for prescreener
   and then whitelist participants who succeed prescreen experiment

.. _section-7:

.. _section-8:

Experiment script
^^^^^^^^^^^^^^^^^

In case of assets, make sure you are not using DebugStorage, but
S3Storage or a LocalStorage.

Add config params under class Exp(psynet.experiment.Experiment):

config = {

\**get_prolific_settings(),

"initial_recruitment_size": 5,

"title": "Put your experiment title here (Chrome browser, ~XX mins)",

"description": “This is speaking experiment that needs to be done in a
quiet place WITHOUT headphones. You will be asked to imitate rhythms.
The task will take about 15 minutes.”(Describe the experiment here, and
clearly mention requirements (e.g., headphones, Chrome browser,
incognito mode, …))

(You can spread your description over several lines, but check how it
looks on Prolific, you might need to add or revisit formatting there
(especially if you use multiple paragraphs))

"Please use incognito mode.",

"contact_email_on_error": "computational.audition@gmail.com",

"organization_name": "Max Planck Institute for Empirical Aesthetics",

"show_reward": False

}

An example for title:

“Check recorded texts (Chrome browser, Headphone required, Native
english speakers only; ~10-15 mins)”

Example for description:

“In this experiment you will hear spoken sentences and need to judge the
quality of their transcript. The experiment requires Chrome browser and
Headphones and is intended for Native English speakers. It lasts 10-12
min.”

You may also want to add other config parameters that are optional,
e.g.,

“force_incognito_mode”: True

Note that we actually recommend force_incognito_mode=True for most
experiments as it makes sure participants actually use incognito. Not
having incognito can generate differences in display if participants are
using browser add-ons. If you don’t care about this display issue you
can set this to False.

This forces people to use an incognito browser, which helps against the
red screen error. For an overview of all options, see
https://psynetdev.gitlab.io/PsyNet/experiment_development/configuration.html

Then, you will need to add the function get_prolific_settings() to set
up config parameters specifically pertaining to Prolific. Add this
function at the top of your project (you can find
qualification_prolific.json in the CAP-safe):

def get_prolific_settings():

with open("qualification_prolific_en.json", "r") as f:

qualification = json.dumps(json.load(f))

return {

"recruiter": "prolific",

"*base_payment*": <base payment in currency>, # this is based on the
amount of minutes of your survey

"prolific_estimated_completion_minutes": <estimated completion time>,

"prolific_recruitment_config": qualification,

"auto_recruit": False,

"currency": "£",

"wage_per_hour": 0 # note that we do that to make everything in base
payment.

}

**Note:** for the time being until we change PsyNet we need to use
wage_per_hour= 0 which means we override the bonus payment system. This
is because currently variable payment is not allowed in prolific and we
simply pay everything as base payment.

-  **Make sure your payment is in line with the estimated completion
   time**; Prolific requires a *minimum of £6 per hour*, based on the
   median completion time across participants in your study. You can
   verify your experiment duration by `having multiple group members
   test out your experiment <#testing-within-the-group>`__ before you
   deploy and checking their median completion time. Keep an eye on this
   while running the experiment with participants!

-  **Do NOT set a value for the ‘id’ parameter in the config**. We do
   not set it to a meaningful name through the config parameters because
   it is shown to participants on the first page of the experiment (in
   the left top corner after ‘Application ID’). If you do not set an
   ‘id’ parameter in config, PsyNet will generate a random hash string
   as ID. In Prolific this ID will show as the internal name of the
   experiment.

Prolific qualifications
^^^^^^^^^^^^^^^^^^^^^^^

Add the qualification_prolific_en.json file to your experiment folder
(You can find it in the cap-safe). This currently specifies
qualifications for collecting data from **English speaking participants
in the UK**. This file will also specify important parameters for
Prolific, such as country of recruitment, participant demographics, etc.

-  You can manually modify the exact demographic requirements in
   Prolific (after you deploy, before you publish). Their GUI will also
   tell you the number of active participants who fulfill these
   criteria.

Deployment
~~~~~~~~~~

**IMPORTANT NOTE:** In **PsyNet 11.9.0** you should add
following settings to .dallingerconfig:

[Prolific]

prolific_workspace = <WORKSPACE_YOU_WANT_TO_USE>

prolific_project = <YOUR_PROJECT_FOLDER>

-  Choose workspace that you want to deploy (check account balance)

.. image:: /_static/images/lab_deployments/image16.png
   :width: 8.5in

-  You should create a project folder for your experiments. Please use
      your own name. For example: ‘Elif Experiments’

.. image:: /_static/images/lab_deployments/image13.png
   :width: 8.5in

Deploy the experiment. Please see `deployment
process <#actual-deployment>`__.

Prolific: check & adapt study details
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before participants can take part in your experiment, you will have to
confirm some settings on Prolific first. For that go to
`prolific.com <https://www.prolific.com/>`__ and login to the group's
account. You can find the credential in the
`cap-safe <https://gitlab.com/computational-audition-lab/cap-safe>`__.

In the “Draft” tab of the “Projects” folder you will find your
experiment:

.. image:: /_static/images/lab_deployments/image14.png
   :width: 8.5in

Click on the ‘ACTION’ button and next on the ‘Move’ button to move the
experiment to your personal experiment folder.

Then click on the name of your experiment. This will lead you to a page
where you can check and adjust some of your experiment parameters. Make
sure that everything is set up the way you intended; especially the
payment parameters! Also check whether the formatting of the description
is as intended.

Here, you should set the internal name to “<your name> -
<keyword/phrase>” (e.g. “ofer - coin game”). This is not visible to
participants. This will help us identify who each study belongs to,
especially when sorting through messages from participants.

Additionally, on this page, you will need to set the approvement process
to “Approve and pay”, otherwise you have to approve all your
participants manually:|image4|

Prolific: estimate & claim experiment cost
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can get an estimate of the total cost of your experiment by setting
the recruitment size to the total number of participants you are looking
to recruit (plus a few more to be safe, if you have a prescreener) and
scrolling down to the “Study Cost” section and finding the total. This
includes the Prolific service fee. **Check whether there is enough
unclaimed money in the Prolific account (if not, contact Nori about
this). Once there is enough unclaimed money, post the estimate to the
#prolific_experiment_claims channel** on Slack, and **set your
recruitment size back to your initial recruitment size**.

.. image:: /_static/images/lab_deployments/image52.png
   :width: 8.5in

.. image:: /_static/images/lab_deployments/image58.png
   :width: 8.5in

Prolific: preview
^^^^^^^^^^^^^^^^^

If you want a final test of your experiment through Prolific, you can do
that if you change the participant_id in the url.

Please note that the data is saved in the database. Typically you want
to run the first trials, but not completing the experiment because your
data is saved as a real participant. In some experiments (like a static
experiment) you can then able to filter the data for participants that
did not finish the experiment.

Prolific: publish experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you are happy with all the settings, click on “publish” to put your
experiment online.

Monitoring
~~~~~~~~~~

Recruitment strategy
^^^^^^^^^^^^^^^^^^^^

It is recommended to start with an initial recruitment size of 5-10
people. After all these initial participants have finished the
experiment, you should check that you do not get any errors and that
your initial time estimate for the experiment is accurate. Only then you
can increase the experiment size manually. To do so click on “Action” on
the upper right side of the prolific dashboard and then on “increase
places”.

.. image:: /_static/images/lab_deployments/image35.png
   :width: 8.5in

The number you set here is the number of the total number of
participants for your experiment. I.e., if you have already 5
participants and you want to get 5 additional participants, this number
has to be 10. Make sure that you do not have too many participants
taking your experiment at once, because this could overload the server
and cause errors and slow-downs.

At any time, you should check for errors (you get an error report on
each export) and make sure that the median wage per hour (indicated on
the prolific dashboard) does not go under the minimum of £6 per hour.

**Auto-recruit**

Auto-recruit is a functionality in psynet that automatically increases
places in your experiment. You can change this parameter from the
experiment dashboard:

.. _section-9:

|image5|
--------

The logic is as follows: Whenever someone completes the study, another
spot will be automatically added. I.e., if you have currently 3 people
taking the experiment and turn it on, then there will always be 3 active
participants.

**You have to be really careful when using this.** In case you use it,
make sure to consider following points:

-  Only use it after you collected the first 10 participants, if you did
   not get any complaints from participants, and if you have checked
   whether the exported data looks ok

-  Stop Auto recruit when you get to 90% of the experiment. After which
   you manually recruit the rest. This is a good idea since in some
   experiments participants are still continuously recruited and have
   very little to do. This way they will be fully compensated but
   contribute very little. To avoid this problem toward the end of the
   experiment stopping auto recruit earlier is a good idea.

-  **Really make sure that auto-recruit is off, when stopping the
   experiment. Clicking on “stop” in the prolific dashboard is not
   enough.**

.. _section-10:

Messages in Prolific
^^^^^^^^^^^^^^^^^^^^

Messages that are specific to your experiment can be seen in the chat
box on the lower right.

It is suggested though, to click on “Messages” on the upper side of the
screen, to see all messages (also messages related to other
experiments).\ |image6|

The reason is that we want to keep our inbox clean and only in this view
can you archive messages. To do so (after you have handled the
participants issue) click on the checkbox of the message and then click
on “archive”.

.. image:: /_static/images/lab_deployments/image32.png
   :width: 8.5in

Answering messages
^^^^^^^^^^^^^^^^^^

Since there can be various reasons why a participant is messaging you,
there is no standard way to answer. Most of the time though, a
participant is messaging you because they have encountered an error in
your experiment. If so, you can look for that participant in the
“participant” tab of your psynet dashboard by pasting their ID from
prolific to the “worker id” field. There you will find a “Link for
resuming session”, which you can send to the participant.

If that does not work or the participant cannot continue the experiment
because of some issue on our side, you should approve them manually. You
can do so by searching for their ID in the prolific dashboard and
clicking on the checkmark. By doing do they will be payed the base
payment you have set in the beginning.

.. image:: /_static/images/lab_deployments/image36.png
   :width: 8.5in

Termination
~~~~~~~~~~~

-  Make sure that there are no participants actively taking the
   experiment

-  Approve/reject people in awaiting review

-  The status of the experiment should be “\ **COMPLETED”**

-  Turn off auto-recruit! Otherwise it will keep recruiting
   participants, even if you stopped the experiment

-  Put experiment in your folder on Prolific.

CINT (Lucid) 🔹 
---------------

.. _setting-up-the-experiment-1:

Setting up the experiment
^^^^^^^^^^^^^^^^^^^^^^^^^

.. _experiment-costs-1:

Experiment costs
^^^^^^^^^^^^^^^^

1) Adjust the “\ **wage_per_hour**\ ” parameter in the config according
   to the minimum wage in the targeted country. A list of minimum wages
   per country can be found at this
   `link <https://docs.google.com/spreadsheets/d/1Yl-eEsLTxFAVyZECZfRQnDlYM8ykY9xlJpnsTpi5oKQ/edit#gid=0>`__.

"wage_per_hour": 6.5

2) Make sure all time_estimates are set appropriately such that the
   overall duration of your experiment (you get from psynet estimate)
   matches your expectation.

3) Run psynet estimate in the terminal and note your estimated
   experiment duration and cost. **DO NOT indicate the cost in your
   experiment’s title, only the duration. Also, say people need Chrome
   and optionally headphones and microphones if needed**.

4) Check that the experiment costs are right:

-  Use your own data (and possibly but not mandatory the group data) to
   estimate how long it takes for each trial, pre-screeners, and the
   entire experiment

-  Start running (if possible) a small number of participants (e.g., 10)
   and try to see if your time estimate is wrong by more than 30% -
   redeploy.

-  If you had run the experiment, update the run time based on real
   data.

.. _experiment-script-1:

Experiment script
^^^^^^^^^^^^^^^^^

In the case of assets, make sure you are not using DebugStorage, but
S3Storage or a LocalStorage.

.. code:: python

   class Exp(psynet.experiment.Experiment):
       config = {
           **recruiter_settings,
           "initial_recruitment_size": 10,  # set to required numbers
           "language": LOCALE,  # set to the ISO-2 language code (e.g. 'tr' or 'en')
           "auto_recruit": False,
           "wage_per_hour": 6.5,  # set to minimum wage of target country
           "title": "Put your experiment title here (Chrome browser, ~XX mins)",
           "contact_email_on_error": "computational.audition+online_running@gmail.com",
           "organization_name": "Max Planck Institute for Empirical Aesthetics",
       }

CINT Recruiter Settings 
^^^^^^^^^^^^^^^^^^^^^^^^

You will need to define recruiter_settings and add the function
get_lucid_settings() to set up config parameters specifically on CINT.
Add this function at the top of your project.

Set the following parameters:

-  lucid_recruitment_config_path: path to qualifications JSON
   file. (see `CINT Qualifications <#cint-qualifications>`__ for
   details)

-  termination_time_in_s: adjust the maximal time a participant
   can spend on the experiment

-  debug_recruiter: Only set it to ‘True’ during local testing

-  initial_response_within_s: Termination of the participant if
   the first response is not reached within that time.

-  bid_incidence: You can adjust the incidence rate here
   according to your experiment’s reports on lucid. Set it to a
   realistic value, but as high as possible.

-  inactivity_timeout_in_s: The inactivity (i.e., no clicking,
   no typing, no scrolling or moving the mouse) timeout in seconds.
   Adjust it according to your experiment design.

-  no_focus_timeout_in_s: Termination of the participant in case
   of moving the mouse outside the window or opening another tab. **This
   is active on all pages! Set it to a realistic value.**

-  aggressive_no_focus_timeout_in_s: The same setting as
   \`no_focus_timeout_in_s\`, but only used on the qualification
   verification pages. **It is important to verify the qualifications on
   the very first page to kick out sloppy participants.**

.. code:: python

   recruiter_settings = get_lucid_settings(
       lucid_recruitment_config_path=LUCID_CONFIG_PATH,
       termination_time_in_s=120 * 60,
       debug_recruiter=False,
       initial_response_within_s=180,
       bid_incidence=66,
       inactivity_timeout_in_s=120,
       no_focus_timeout_in_s=60,
       aggressive_no_focus_timeout_in_s=3,
   )

CINT Consent
^^^^^^^^^^^^

You need to use CINT (Lucid) consent while deploying to CINT.

1) Import it from psynet.consent

.. code:: python

   from psynet.consent import LucidConsent

2) Define the consent parameter in your experiment.py

.. code:: python

   consent = LucidConsent

3) Make sure to add consent() function to your timeline. (Please
   note that additional audiovisual consent may be needed depending on
   your experiment.)

CINT Qualifications
^^^^^^^^^^^^^^^^^^^

Setting Qualifications Automatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CINT has a standard qualification library and you can create custom
qualifications.

Currently, we have the following custom qualifications:

-  [\`\ `TIMEOUT <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=187e22aa-8a67-45c9-8a7c-481eeeaddfb0>`__\ \`]:
   warning participants they can't leave the page as they might be
   kicked out otherwise (set automatically)

-  [\`\ `MONOLINGUALISM <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=08a162fe-4c14-48c7-b850-1d09f95527a1>`__\ \`]:
   asking participants if they are monolingual

-  [\`\ `HAS_AUDIO <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=25434891-030a-405a-9616-e43961d674fa>`__\ \`]:
   asking participants if they can play audio

-  [\`\ `ALLOW_VOICE_RECORDING <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=9242d802-f6d6-4786-8049-50490dcd5179>`__\ \`]:
   asking participants if they can record their voice

-  [\`\ `BORN_IN_COUNTRY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=2a6d41c7-c38c-4a69-ad12-2cca5074d98f>`__\ \`]:
   asking participants if they were born in the country

-  [\`\ `HAS_NATIONALITY <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=f91c6b4f-7167-4e30-95ab-9efb408f0537>`__\ \`]:
   asking participants

-  [\`\ `IS_NATIVE <https://www.samplicio.us/fulcrum/QuestionDetails.aspx?QuestionSID=c0833d98-be26-46df-8e01-1abbb740cda6>`__\ \`]:
   asking participants if they are native speakers

There are a variety of languages and countries available on CINT with
specific tags. You can get a list of all the available language (3
capital letters) and country (2 capital letters) tags by running the
following code in your terminal:

.. code:: bash

   psynet lucid locale

After getting the desired locales, you can generate qualifications
specific to each country by using a custom create_qualifications.py.
Please find an example code below that you can adjust and add to your
create_qualifications.py.

.. code:: python

   from tqdm import tqdm
   from psynet.lucid.qualifications import create_lucid_recruitment_config

   country_language_tags = (("DUT", "NL"),)

   for language_tag, country_tag in tqdm(country_language_tags):
       config_path = f"qualifications/lucid/lucid-{language_tag}-{country_tag}.json"
       create_lucid_recruitment_config(
           language_tag=language_tag,
           country_tag=country_tag,
           question_answer_dict={
               "MONOLINGUALISM": ["I was raised with my native language only"],
               "HAS_AUDIO": ["Yes"],
               "ALLOW_VOICE_RECORDING": ["Yes"],
               "BORN_IN_COUNTRY": ["Yes"],
               "HAS_NATIONALITY": ["Yes"],
               "IS_NATIVE": ["Yes"],
           },
           config_path=config_path,
           debug=True,
       )

Extending the qualification to new languages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can expand an existing qualification for a new language. Go to the
qualification page and add the question and the options. Make sure that
the options are in the same order as in the original. It is recommended
to use the English language as a reference so that the options match up.

.. _section-11:

Adding a new qualification
~~~~~~~~~~~~~~~~~~~~~~~~~~

Go to the [`qualification overview
page <https://www.samplicio.us/fulcrum/Questions.aspx>`__] and click the
button "Add Qualification". Now set the Qualification Name. It is
recommended to use only capital letters and underscores
(e.g.`HAS_AUDIO\`). For the Qualification Type, select "Conditional List
– Single Punch". Set Minimum Displayed Conditions and Maximum Displayed
Conditions to 2. Now click "Save". Move down to "Step 2: Questions".
Click "Add Question Text". Select the language country pair you want to
add. Add the question text. Now add the options with line breaks in
"Mass Upload" and select the right language pair. Click "Save".

It takes some time for CINT to register new custom qualifications. If
you want to use it in your experiment, go to your qualification page,
right-click in Chrome on the page, and select "View Page Source". Now
search for "QuestionID", this field is the ID of the qualification. You
can now use this ID in your experiment:

.. code:: python

   from psynet.experiment import get_and_load_config
   from psynet.lucid import get_lucid_service
   from psynet.lucid.qualifications import create_lucid_recruitment_config

   language_tag = "DUT"
   country_tag = "NL"
   config_path = f"qualifications/lucid/lucid-{language_tag}-{country_tag}.json"

   config = get_and_load_config()
   service = get_lucid_service(config=config)
   custom_qualifications_dict = {
       **service.get_qualifications_dict(),
       "MY_NEW_QUALIFICATION": 200093,  # replace 200093 with actual ID
   }

   create_lucid_recruitment_config(
       language_tag=language_tag,
       country_tag=country_tag,
       question_answer_dict={
           "MONOLINGUALISM": ["I was raised with my native language only"],
           "HAS_AUDIO": ["Yes"],
           "ALLOW_VOICE_RECORDING": ["Yes"],
           "BORN_IN_COUNTRY": ["Yes"],
           "HAS_NATIONALITY": ["Yes"],
           "IS_NATIVE": ["Yes"],
       },
       config_path=config_path,
       debug=True,
       config=config,
       service=service,
       qualifications_dict=custom_qualifications_dict,
   )

Front-end confirmation of qualifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is recommended to let users confirm the qualifications in the
front-end. There are multiple reasons for this:

-  First, on the qualification pages, we have strict rules concerning
   how long they can leave the page. Since the majority of participants
   leave the experiment on the first page, this is a good way to
   terminate them here. Also, since this is fairly fast, it will reduce
   the termination LOI.

-  Second, it is good to double-check the requirements.

To do this, you can use the following code:

.. code:: python

   import psynet.experiment
   from psynet.consent import LucidConsent
   from psynet.timeline import Timeline
   from psynet.page import SuccessfulEndPage
   from psynet.lucid.qualifications import verify_lucid_qualifications

   LANGUAGE = "DUT"
   COUNTRY = "NL"
   LUCID_CONFIG_PATH = f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"

   class Exp(psynet.experiment.Experiment):
       timeline = Timeline(
           verify_lucid_qualifications(LUCID_CONFIG_PATH),
           LucidConsent(),
           SuccessfulEndPage(),
       )

If you don't want to show all qualifications to the participants or want
to show them in a different order, you can specify them as an additional
argument:

.. code:: python

   verify_lucid_qualifications(
       LUCID_CONFIG_PATH,
       question_names=["TIMEOUT", "MONOLINGUALISM"],
   )

.. _section-12:

Summary Steps for Setting CINT Qualifications:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1) Access a list of available language and country tags using the
   command psynet lucid locale.

2) Use the provided Python script to create predefined qualifications
   (e.g.`HAS_AUDIO\`) specific to each country.

3) Be sure that you have added the following parameters to your
   experiment.py:

.. code:: python

   LANGUAGE = "DUT"  # lucid language code, not ISO language code
   COUNTRY = "NL"  # lucid country code, not always ISO country code
   LOCALE = "nl"  # ISO-2 code for experiment language
   LUCID_CONFIG_PATH = f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"

4) Implement front-end confirmation of qualifications to ensure
   participant adherence to requirements and improve termination
   efficiency. Optionally, you can specify which qualifications to
   display and their order using additional arguments in the front-end
   confirmation code. Adjust and add the following code to your
   timeline.

.. code:: python

   verify_lucid_qualifications(
       LUCID_CONFIG_PATH,
       question_names=["TIMEOUT", "MONOLINGUALISM"],
   )

.. _deployment-1:

Deployment
~~~~~~~~~~

CINT: check & adjust quota
^^^^^^^^^^^^^^^^^^^^^^^^^^

After you deploy, go to `CINT
marketplace <https://auth.lucidhq.com/u/login/identifier?state=hKFo2SBEOHYxNU9ac25wQ3Y1ajlZSUhJX0gxcnF3eS1jSjFUU6Fur3VuaXZlcnNhbC1sb2dpbqN0aWTZIHBoMGRGTFdKMEoyQU9rRjAtaGtPWHRJMXdwQ2V2M3Zio2NpZNkgdFZ2aUpIUUc2VUV6dkw4Z3hwQVBoNG9jNWg5ajl6Z2o>`__
and log in to the group's account. You can find the credentials in the
`cap-safe <https://gitlab.com/computational-audition-lab/cap-safe>`__.

Also, save and open the link provided in the terminal after successful
deployment to `monitor <#monitoring-1>`__ the experiment. When you open
the link, you will see the dashboard. Here, click on the ‘Lucid’ tab to
access many features from the marketplace as well as the reports of the
experiment.

.. image:: /_static/images/lab_deployments/image34.png
   :width: 8.5in

1) **Checking qualifications:** Here, click the “Qualifications” tab to
   check if the qualifications are set correctly. This will direct you
   to the official marketplace site.

.. image:: /_static/images/lab_deployments/image30.png
   :width: 8.5in

.. image:: /_static/images/lab_deployments/image53.png
   :width: 8.5in

2) **Adjusting quota:** To manage the quota settings, go to the ‘Quota’
   tab. This will direct you to the official marketplace site.

.. image:: /_static/images/lab_deployments/image10.png
   :width: 8.5in

There are two types of calculations in CINT: completed and prescreens.
Completes are when a survey fills based on respondents that complete the
survey. Prescreens are when a survey fills based on respondents that
complete the Marketplace prescreener. By default, deployments are set to
'Completes.' However, it's advisable to consider switching to
'Prescreens' and setting a quota at the outset of your experiment. This
proactive measure helps prevent server overload, especially during
periods of high participant influx, which could otherwise lead to
experiment crashes. To implement this, navigate to the 'CALCULATION
TYPE' and switch to 'Prescreens.' Begin by setting a modest quota, such
as 10, then gradually adjust it based on experiment progression and
participant traffic. You can change it back to ‘Completes’ if the
experiment pace slows down.

.. image:: /_static/images/lab_deployments/image6.png
   :width: 8.5in

.. _monitoring-1:

Monitoring 
~~~~~~~~~~~

The new interface under the ‘Lucid’ tab in the dashboard offers a
variety of ways to monitor the experiment.

1. Check how many participants are working, terminated, and completed.
   It is important to inspect ‘Termination reasons’ as it might reveal
   if something is wrong with the experiment.

.. image:: /_static/images/lab_deployments/image46.png
   :width: 8.5in

2. Check the vital metrics of the experiment. Note that they are usually
   not optimized at the beginning of the experiment so you need to wait
   a little to see the realistic results:

-  **Conversion rate** gives the percentage of respondents who complete
   the study after exiting the Marketplace prescreener. To increase the
   conversion rate you can build quotas into the Marketplace to avoid
   client side over quotas. It should be higher than 10%.

-  **Dropoff rate** gives the percentage of respondents who passed the
   qualifications but did not return to the Marketplace. This should be
   less than 20%. If this is high you should look for possible setup
   errors i.e. routing, images/videos are displayed correctly

-  **Incidence rate** gives the percentage of respondents that will
   qualify for the study after qualification targeting. It is set to 66%
   by default on psynet lucid setting. You should aim for as high a
   number as possible. However, you can change it to a lower value if
   necessary. Use the bid_incidence parameter in the
   get_lucid_settings() to change it.

-  **EPC (Earnings Per Click)** measures the gross dollar amount a
   supplier can expect for each respondent they send into a survey,
   indicating whether the survey is appropriately priced. EPCs of $0.20
   - $0.30 are considered healthy, whereas EPCs below $0.15 will
   struggle to attract supplier traffic. Find more information
   `here <https://support.lucidhq.com/s/article/EPC-FAQ>`__.

.. image:: /_static/images/lab_deployments/image49.png
   :width: 8.5in

3. Check how many participants enter the survey overtime on the
   ‘Respondents’ graph. If it is dying out, you may need to adjust the
   quota.

.. image:: /_static/images/lab_deployments/image11.png
   :width: 8.5in

4. Monitor participant status across survey pages by clicking on bars to
   access participant IDs and termination reasons. It is typical to have
   a high termination rate at the early stage of the experiment.

.. image:: /_static/images/lab_deployments/image4.png
   :width: 8.5in

5. Check completion LOI and termination LOI. The completion LOI should
   match your time estimate. Termination LOI should be low as much as
   possible. If it is higher than expected you should inspect for
   possible errors in your experiment.

.. image:: /_static/images/lab_deployments/image56.png
   :width: 8.5in

.. _section-13:

.. _termination-1:

Termination
~~~~~~~~~~~

Once you reach the desired number of participants, set it to ‘Complete’
and `export <#_vlrp8nxplekx>`__ your data again. To destroy the app,
wait until there are no more working participants left in the
experiment.

.. image:: /_static/images/lab_deployments/image9.png
   :width: 8.5in

Reconciling participants
^^^^^^^^^^^^^^^^^^^^^^^^

If people are terminated for the wrong reasons or errors occurred in the
experiment, you need to reconcile your survey. Your survey must have the
status completed.

You can compensate with the following command:

.. code:: bash

   psynet lucid compensate SURVEY_NUMBER RID_1 RID_2 […] RID_N

You need to add all completed RIDs, **so also those that are already
marked as completed! Otherwise, already completed participants are
marked as terminated!**

Lab Recruiter 🔹 
----------------

The Group Manager (usually the experimenter) is responsible for setting
up and managing participant recruitment through Lab Recruiter. The
system provides full control over participant selection, experiment
access, and tracking.

Registering to the CAP Platform
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create an Admin account
^^^^^^^^^^^^^^^^^^^^^^^

-  For now, please contact us at coco-experiments@cornell.edu to
      have your admin account created in the Lab Recruiter app.

Create a Group
^^^^^^^^^^^^^^

-  As the Group Manager, go to the Group tab and click **‘New**
      **Group’** to create a participant group.

.. image:: /_static/images/lab_deployments/image3.png
   :width: 8.5in

Set an Initial Test
~~~~~~~~~~~~~~~~~~~

-  In your group settings, you can enable an "Initial Test Experiment"
      designed to verify device compatibility—including headphone
      functionality and audio quality. Participants must complete this
      test before accessing any actual experiments, ensuring they meet
      the necessary technical standards. If your experiments have
      additional requirements, please contact us for further assistance.

.. image:: /_static/images/lab_deployments/image38.png
   :width: 8.5in

.. _setting-up-the-experiment-2:

Setting up the experiment
~~~~~~~~~~~~~~~~~~~~~~~~~

.. _experiment-costs-2:

Experiment costs
^^^^^^^^^^^^^^^^

1) We typically pay 15 Euros per hour. So adjust the
      “\ **wage_per_hour**\ ” parameter in the config accordingly.

"wage_per_hour": 15

2) Make sure all time_estimates are set appropriately such that the
      overall duration of your experiment (you get from psynet estimate)
      matches your expectation.

3) Run psynet estimate in the terminal and note your estimated
      experiment duration and cost.

4) Check that the experiment costs are right:

-  Use your own data (and possibly but not mandatory the group data) to
   estimate how long it takes for each trial, pre-screeners, and the
   entire experiment

-  Start running (if possible) a small number of participants (e.g., 10)
   and try to see if your time estimate is wrong by more than 30% -
   redeploy.

-  If you had run the experiment, update the run time based on real
   data.

.. _experiment-script-2:

Experiment Script
^^^^^^^^^^^^^^^^^

In case of assets, make sure you are not using DebugStorage, but
S3Storage or a LocalStorage.

Add config params under class Exp(psynet.experiment.Experiment) and set
recruiter as 'lab-recruiter':

config = {

“recruiter”: "lab-recruiter”,

"initial_recruitment_size": 5,

"title": "Put your experiment title here (Chrome browser, ~XX mins)",

"description": “This is speaking experiment that needs to be done in a
quiet place WITHOUT headphones. You will be asked to imitate rhythms.
The task will take about 15 minutes.”(Describe the experiment here, and
clearly mention requirements (e.g., headphones, Chrome browser,
incognito mode, …)),

"contact_email_on_error": "computational.audition@gmail.com",

"organization_name": "Max Planck Institute for Empirical Aesthetics",

"show_reward": False

}

An example for title:

“Check recorded texts (Chrome browser, Headphone required, ~10-15 mins)”

Example for description:

“In this experiment you will hear spoken sentences and need to judge the
quality of their transcript. The experiment requires Chrome browser and
Headphones and is intended for Native English speakers. It lasts 10-12
min.”

Consent
^^^^^^^

You can choose the consent while creating the group. Currently we are
using ‘Cornell University’. Please contact if you want to create your own consent
form.

.. image:: /_static/images/lab_deployments/image1.png
   :width: 8.5in

.. _deployment-2:

Deployment
~~~~~~~~~~

Deploy the Experiment. Please see `deployment
process <#actual-deployment>`__.

-  After deploying your experiment, navigate to the Experiments tab.

-  Click **‘New Experiment’** to add your experiment to the Lab Recruiter.

.. image:: /_static/images/lab_deployments/image28.png
   :width: 8.5in

-  Here please set the required parameters.

   -  **Estimated Duration:** This is the predicted duration of the
         experiment.

   -  **Maximum Duration:** This is the total time participants are
         allowed to remain in the experiment before being timed out.

   -  **Batches:** This specifies the number of times each participant
         can take part.

   -  **URL:** This is the link provided on the console after deployment
         (e.g., https://your-app-name.experiments1.cococo-lab.cornell.edu).

-  At the bottom of the page move your Group from “Available groups” up
      into the **‘Groups’** section to make the experiment accessible to
      all participants in that group.

.. image:: /_static/images/lab_deployments/image48.png
   :width: 8.5in

.. _section-14:

-  You can also later edit it by click **‘Edit’** on your experiment.

.. image:: /_static/images/lab_deployments/image27.png
   :width: 8.5in

Inviting Participants
~~~~~~~~~~~~~~~~~~~~~

Invite Participants
^^^^^^^^^^^^^^^^^^^

-  Once the setup is complete, go to the Groups tab.

-  Click ‘\ **Copy Invitation Link**\ ’ for your group.

-  Send this link to participants via email.

-  Participants registering with this link will automatically use the
      Group Manager code for your group.

.. image:: /_static/images/lab_deployments/image18.png
   :width: 8.5in

Send Messages 
^^^^^^^^^^^^^^

-  Using the messages option, you can send emails to participants in
      each group. Simply compose your message—such as informing them
      about a new study—and choose whether to send it to all
      participants or only specific individuals from the recipients
      list. The message is then sent from the Lab Recruiter official
      email account to the selected group.

.. image:: /_static/images/lab_deployments/image21.png
   :width: 8.5in

Monitor and Manage Participants
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dashboard
^^^^^^^^^

Use your experiment dashboard to monitor your experiment. See
`dashboard <#using-the-dashboard>`__.

Participant tracking
^^^^^^^^^^^^^^^^^^^^

-  Track participant progress in the Participants tab (experiments
      taken, payment status, etc.).

.. image:: /_static/images/lab_deployments/image20.png
   :width: 8.5in

Managing Experiment Tasks
^^^^^^^^^^^^^^^^^^^^^^^^^

-  Reset failed experiments by navigating to ‘Tasks’ and clicking the
      **‘Reset’** button.

.. image:: /_static/images/lab_deployments/image39.png
   :width: 8.5in

.. _termination-2:

Termination
~~~~~~~~~~~

Experiment Completion
^^^^^^^^^^^^^^^^^^^^^

-  Upon completion or failure, experiment status, time tracking, and
      payment records are updated. Payments are processed externally by
      the lab team so please **DO NOT** press the ‘\ **Payment Done**\ ’
      button for the completed participants.

Terminate the Experiment
^^^^^^^^^^^^^^^^^^^^^^^^

-  Once you reach the desired number of participants, export your data
      again and set it to **‘Archive’** on the Lab Recruiter.

-  You also need to delete the experiment from the server. Please see
      `teardown <#teardown>`__.

Lab Recruiter For Participants
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Sign Up & Verification

   -  Sign up to Lab Recruiter using the unique Group Manager code
         received via email.

   -  Verify your email to activate your account.

2. Accessing Experiments

   -  Through the Lab Recruiter interface, participants can:

      -  View available experiments.

      -  Access experiment details and links.

      -  Track their payment status.

.. image:: /_static/images/lab_deployments/image54.png
   :width: 8.5in

3. Initial Test Experiment

   -  Participants complete an initial test experiment to verify device
         compatibility:

      -  Successful participants gain access to real experiments.

      -  Unsuccessful participants can retry the test if the experiment
            resets their attempt.

4. Experiment Participation

   -  Once eligible, participants can take available experiments from
         the Lab Recruiter platform.

5. Completion & Payment

   -  Experiment status is updated automatically, and payment is
         processed externally by the lab team regularly every two weeks.

Report & Deposit
================

Pol is working on this

Troubleshooting
===============

**Q**: Help, I can’t access my server anymore!

| **A**: Try re-adding your pem file to your ssh keygen by running:
| ``ssh-add -K ~/cap.pem``

**Q**: I get this error after running ``psynet debug ssh`` or
``psynet deploy ssh``. What
should I do?

.. code:: text

   docker.errors.DockerException: Error while fetching server API version:
   ('Connection aborted.', ConnectionRefusedError(61, 'Connection refused'))

**A**: You should make sure Docker Desktop is running.

**Q:** When debugging, I obtain the following (similar) error:

.. code:: text

   docker.errors.DockerException: Error while fetching server API
   version: ('Connection aborted.', PermissionError(13, 'Permission denied'))

**A**: Changing permissions to the docker socket appears to have
resolved this issue for me.

**Q:** Port 5000 is already used

**A:** Disable Airdrop receiver

Alternatively stop another experiment that is running in another window
or pycharm project window. To kill all running python you can write
*killall Python* or *killall python* in the terminal window.

**Q:** My server restarted and my experiment is not running anymore.

**A:** All experiments are stored under ~/dallinger. You can cd into
this directory and cd into the experiment folder. You can now run docker
compose which will restart your experiment docker container.

**Q:** How to compensate a participant who was timed out by Prolific and
is complaining?

**A:** cap prolific approve <study_id> <participant_id>

**Q:** I'm unable to connect to my AWS EC2 instance via SSH; the
connection times out. How can I resolve this issue and regain access to
my server?

A: The timeout error you're receiving often indicates a networking or
internal system issue on the instance that can be resolved with a
reboot. Please follow these steps to reboot:

1. Install AWS CLI

2. Configure it with credentials etc: aws configure

3. Find the instance ID, e.g. from the .. code:: bash

   dallinger ec2 list instances
      command

4. Reboot instance: aws ec2 reboot-instances --instance-ids
      <INSTANCE_ID>

**Q:** A

**A:** A

Things to discuss
-----------------

-  Which server should be used?

-  How many participants should take the experiment at the same time?

-  [STRIKEOUT:Why are we not using prolific version of auto recruit?]

-  [STRIKEOUT:What are the important config params?]

-  [STRIKEOUT:Where to get the prolific_qualifications_en.json ?]

-  How to safely transfer cap.pem and dallingerconfig to new lab
      members?

-  What is our payment strategy?

-  How to use dozzle? How to interpret total CPU usage? Is it ok if it
      spikes above 100%? What are the containers?

-  naming conventions of server, app

-  [STRIKEOUT:reporting of experiment. Will this be automated?]

-  [STRIKEOUT:exporting data while participants are still taking the
      experiment may cause errors [?]]

.. _section-15:

.. |image1| image:: /_static/images/lab_deployments/image19.png
   :width: 8.5in
.. |image2| image:: /_static/images/lab_deployments/image50.png
   :width: 8.5in
.. |image3| image:: /_static/images/lab_deployments/image22.png
   :width: 8.5in
.. |image4| image:: /_static/images/lab_deployments/image33.png
   :width: 8.5in
.. |image5| image:: /_static/images/lab_deployments/image5.png
   :width: 8.5in
.. |image6| image:: /_static/images/lab_deployments/image45.png
   :width: 8.5in
