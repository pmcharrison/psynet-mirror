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

.. code:: ini

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
