Running a demo
==============

The goal of this exercise is to run a demo experiment in debug mode.
Once you have an experiment running in debug mode, it's easy to make small tweaks
and immediately test the results.

Setting up your environment
---------------------------

Before continuing, make sure you have followed the
:doc:`installation instructions <../installation/index>` for your operating system.

You will then need a local checkout of the PsyNet repository so that you have access to its
demos.

.. code-block:: bash

    git clone https://gitlab.com/PsyNetDev/PsyNet.git
    cd PsyNet

Create a virtual environment for the tutorial and install the demo's dependencies.
We suggest using `uv <https://docs.astral.sh/uv/>`_, but ``python -m venv`` also works.

.. code-block:: bash

    uv venv
    source .venv/bin/activate

You will install the dependencies on a per-demo basis, because each demo has
its own ``constraints.txt`` file pinning compatible versions of PsyNet and its
dependencies.

Choose an experiment to run from the ``demos/`` directory.
Let's say we want to run the ``simple_rating`` pipeline. We can do this as follows:

.. code-block:: bash

    cd demos/pipelines/simple_rating
    uv pip install -r constraints.txt
    psynet debug local

.. note::

    Whenever we write a ``cd`` command in this tutorial, we assume you are starting from
    the root of the PsyNet repository. If you have moved away, you can return with
    ``cd path/to/PsyNet``.

.. note::

    ``psynet debug local`` runs on port 5000 by default, which may be occupied
    on macOS systems with AirPlay enabled. If you see an error about the port
    being occupied, you can add ``port = 5001`` (or another port of your choice)
    to your experiment's ``config.txt`` file and try again.

If everything works successfully, a couple of browser windows should open: one
contains the experiment dashboard, and the other contains the participant interface.
If this doesn't happen, check the terminal output for any errors.

Try taking a few pages as a participant, and check that the pages advance appropriately.

Viewing your data
-----------------

Once you have taken a few pages yourself, and ideally seen an experiment trial or two,
you can also check out the dashboard to see your own data.
Click the "Database" dropdown in the navbar and then select "Participant".
You should see a table containing one row, which corresponds to you as a participant.
Scroll to the right to see various attributes that have been stored.
If you click again on "Database" you should also see somewhere some variant of "Trial"
(e.g. "CustomTrial"), depending on the experiment you ran.
Click on this, and you should see one row for each trial you've seen so far.

Making changes to the experiment
--------------------------------

Your next task is to try making some minor changes to the experiment code.
For now, just limit yourself to changing the text displayed to the participant.
Look at the participant page currently visible, and try to find the part of the code
that is responsible for displaying it.
Change some of the text, save the file, then refresh the participant page.
You should see the changes you made.

.. note::

    Cosmetic changes to experiment code (e.g. changing display text) can be viewed
    immediately by refreshing the participant page.
    More substantial changes (e.g. adding new stimuli) require you to stop the debug
    session and start a new one.

Shutting down the session
-------------------------

When you are done with your debug session, you can shut it down by pressing
``Ctrl+C`` in the terminal.
