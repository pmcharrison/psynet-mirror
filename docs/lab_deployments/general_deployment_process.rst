General Deployment Process
==========================

Experiment lifecycle
--------------------

Experiments follow a relatively fixed lifecycle.

-  `Design <#design>`__: Start with a research question and design an
   experiment that can answer it. Discuss the design with collaborators,
   group members, or ``#online-experiments`` on Slack before
   implementation.

-  `Test <#test>`__: Test the experiment automatically, on yourself, and
   with a small group of colleagues or friends.

-  `Provision <provisioning.html#provisioning>`__: Prepare the server
   that will host the experiment. Use an internal server when appropriate
   or provision an EC2 server when participant location or capacity
   requires it.

-  `Deploy <deploying.html#deploying>`__: Launch the experiment for real
   participants. For a first deployment, start with a pilot.

-  `Monitor <monitoring_and_managing.html#monitoring-managing>`__: Watch
   the experiment during data collection, check for errors, review data
   quality, and compensate participants when needed.

-  `Export & Terminate <exporting_and_terminating.html>`__: Export the
   data, run preliminary checks, and terminate the experiment once data
   collection is complete.

-  `Teardown <teardown.html>`__: If you used an EC2 server, turn it off
   when you are done.

-  `Report & Deposit <report_and_deposit.html#report-deposit>`__: Report
   experiment details such as cost, duration, and participant count, then
   deposit the collected data. This procedure is still under
   construction and may change.

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

-  Define the question you want to answer and design an experiment that
   addresses it.

-  Get feedback from collaborators, group members, and Nori.

-  Once you settle on an idea, look for a PsyNet demo that implements
   some of the relevant components. You may need building blocks from
   multiple demos, or in some cases custom PsyNet functionality.

-  A central philosophy of the group is to help each other get unstuck.
   If you encounter a technical or design problem and have already spent
   a reasonable amount of time on it, ask for help:

   -  Post technical problems in ``#psynet-support`` or design questions
      in ``#online-experiments`` on Slack.

   -  Raise the issue during standing.

Test
----

Testing workflows

Testing on yourself
^^^^^^^^^^^^^^^^^^^

It’s important to run the full experiment on yourself, as if you were a
real participant. This will give you a sense of how difficult the task
is, what the appropriate ``time_estimate`` of your task is, etc. Try to
catch edge cases, e.g. when you summarize nodes. One way to achieve this
is by running a smaller number of networks.

The easiest way to test on yourself is to run the experiment locally
from your experiment folder. For a virtual-environment installation:

.. code:: bash

   psynet debug local

For a Docker installation, see the
`Docker installation guide <https://psynetdev.gitlab.io/PsyNet/installation/docker_installation/index.html>`__
for the equivalent command.

If you are using a group Docker registry, make sure you are logged in
before running any Docker-based commands:

.. code:: bash

   docker login registry.gitlab.com

Testing with bots
^^^^^^^^^^^^^^^^^

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

Pilot testing with colleagues
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before publishing your experiment to real participants, it is strongly
recommended that colleagues or collaborators take the experiment in
hotair mode so you can get qualitative feedback:

-  Set up a shortened test version of the experiment if needed.

-  Set your ``recruiter`` config parameter to ``hotair``.

-  `Provision a server <provisioning.html#provisioning>`__ and run
   a remote debug session from your experiment directory:

   .. code:: bash

      psynet debug ssh --app <app_name> --dns-host <your-subdomain>.<your-domain> --server <your-subdomain>.<your-domain>

   This command produces a single recruitment link. Save it.

-  Try the experiment yourself on the remote server to confirm it works
   end-to-end before sharing the link.

-  Share the link with colleagues and ask them to take the experiment.
   Note any aspects you would like specific feedback on.

-  Once you have data, use it to write or verify your analysis code.
   Check that data are processed correctly and that edge cases behave
   as expected.

Since pilot groups are typically small, you may not surface issues that
appear with many simultaneous participants or late in a long-running
experiment. This is why `Testing with bots <#testing-with-bots>`__ is
a complementary step.

Automatic Translation
---------------------

PsyNet supports automatic machine translation so you can run your
experiment in different languages. PsyNet currently supports two
translation backends:

- **OpenAI ChatGPT** (default): requires an OpenAI API key.
- **Google Translator**: requires a Google Cloud service account JSON
  file.

For full setup instructions for each backend, see the
`Internationalization tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/internationalization.html>`__.

Usage
^^^^^

Translating your experiment is straightforward:

1. Set the locale of your experiment. In ``experiment.py``:

   .. code:: python

      class Exp(psynet.experiment.Experiment):
          config = {
              'locale': 'tr',  # ISO 639-1 code, e.g. 'tr' for Turkish
          }

   Or add the following line to your ``config.txt``:

   .. code:: text

      locale = tr

2. Mark strings for translation in your ``experiment.py``:

.. code:: python

   from psynet.utils import get_translator

   _ = get_translator()

   page = InfoPage(
       _("This text will be translated to the locale you set in the experiment")
   )

3. Run translation from the experiment directory:

   .. code:: bash

      psynet translate

Read the `full internationalization tutorial <https://psynetdev.gitlab.io/PsyNet/tutorials/internationalization.html>`__
for information on configuring backends, reviewing translations with
POedit, and handling multi-locale experiments.

Recruiters
----------

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

-  **Lab Recruiter** (LR) is an internally established recruitment
   system that offers full control over participant selection without
   third-party involvement. Labs that run their own Lab Recruiter
   instance can use it to recruit from their own participant pool.
