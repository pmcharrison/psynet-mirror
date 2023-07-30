=====
Tests
=====

Writing automated tests is an essential part of writing reliable software.
Automated tests are scripts that check the functionality of your program
and verify that it is working correctly.
PsyNet provides easy-to-use tools for writing tests for your own
experiment implementations; we recommend you use them whenever
designing your own experiment.

All the demos in the PsyNet package are set up already with simple
automated tests. For this tutorial, we recommend you open up the
``static_audio`` demo to see how this is done.

The convention is for PsyNet experiment directories to contain a
single ``test.py`` file. This ``test.py`` file does not typically
contain any experiment-specific code; every demo has the same file.
This file uses the ``pytest`` package to invoke a generic testing method
defined on the Experiment class.
You can run this test by navigating to the experiment directory
and entering the following in your command line:

::

    pytest test.py

or, if using PsyNet within Docker:

::

    bash docker/run pytest test.py

This command takes a few moments to start as it has to spin up a
PsyNet local server. Once the server is ready,
the ``Experiment.test_experiment`` method is called.
This creates one or more 'bots', or virtual participants;
these bots progress through the experiment one page at a time.
Once the bots all reach the end of the experiment, and all relevant
checks have passed, the test script concludes.
If an error occurs, then a traceback is printed, giving you a
chance to debug it.

.. code-block:: python

    class Experiment(...):
        ...

        test_n_bots = 1

        def test_experiment(self):
            os.environ["PASSTHROUGH_ERRORS"] = "True"
            os.environ["DEPLOYMENT_PACKAGE"] = "True"
            bots = self.test_create_bots()
            self.test_run_bots(bots)
            self.test_check_bots(bots)

The default behavior of the ``test_experiment`` is to create
one bot and run it through the entire experiment, one page at a time.
Unless you tell it otherwise, the bot will generate a random plausible
response for most page types. For example, if the page asks for
a multiple-choice response, the bot will typically choose its response
at random. This behavior can be customized by setting the ``bot_response``
argument when a page is created, either to a fixed value that the
bot always returns (e.g. ``True``), or to a function that is invoked
each time the bot reaches that page.

The 'static audio' demo shows an example where audio is recorded
from a participant. In this case we set
``bot_response_media="example-bier.wav"`` within the
``AudioRecordControl``; this tells the test to use the ``example-bier.wav``
file as the bot's response in all cases.

.. code-block:: python

    AudioRecordControl(duration=3.0, bot_response_media="example-bier.wav")

By default all the test does is check that the bot can get to the
end of the experiment without errors. However it's often sensible
to implement some additional checks to make sure that the state of
the experiment is as you expect it. One way of doing this
is to override the ``Experiment.test_check_bot`` method.
This method is run when the bot completes the experiment.
At this point you can run some custom code to check that the
bot has the right status. In the 'static audio' demo, ``test_check_bot``
is used to verify that the bot has taken the right number of trials.

.. code-block:: python

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.alive_trials) == len(nodes)

These customizations are often enough for simple use cases.
However, it's possible to provide arbitrarily complex logic for these
tests. For an example of a complex test, have a look at the
"rock, paper, scissors" demo, which has multiple bots take the experiment
at the same time, and coordinates how they step through the experiment
together.

.. code-block:: python

    class Experiment(...):
        ...

        test_n_bots = 2

        def test_run_bots(self, bots: List[Bot]):
            from psynet.page import WaitPage

            advance_past_wait_pages(bots)

            page = bots[0].get_current_page()
            assert page.label == "choose_action"
            bots[0].take_page(page, response="rock")
            page = bots[0].get_current_page()
            assert isinstance(page, WaitPage)

            page = bots[1].get_current_page()
            assert page.label == "choose_action"
            bots[1].take_page(page, response="paper")

            advance_past_wait_pages(bots)

            pages = [bot.get_current_page() for bot in bots]
            assert pages[0].content == "You chose rock, your partner chose paper. You lost."
            assert pages[1].content == "You chose paper, your partner chose rock. You won!"

            bots[0].take_page()
            bots[1].take_page()
            advance_past_wait_pages(bots)

            bots[0].take_page(page, response="scissors")
            bots[1].take_page(page, response="paper")
            advance_past_wait_pages(bots)

            pages = [bot.get_current_page() for bot in bots]
            assert (
                pages[0].content == "You chose scissors, your partner chose paper. You won!"
            )
            assert (
                pages[1].content
                == "You chose paper, your partner chose scissors. You lost."
            )

            bots[0].take_page()
            bots[1].take_page()
            advance_past_wait_pages(bots)

            bots[0].take_page(page, response="scissors")
            bots[1].take_page(page, response="scissors")
            advance_past_wait_pages(bots)

            pages = [bot.get_current_page() for bot in bots]
            assert (
                pages[0].content
                == "You chose scissors, your partner chose scissors. You drew."
            )
            assert (
                pages[1].content
                == "You chose scissors, your partner chose scissors. You drew."
            )

            bots[0].take_page()
            bots[1].take_page()
            advance_past_wait_pages(bots)

            pages = [bot.get_current_page() for bot in bots]
            for page in pages:
                assert isinstance(page, SuccessfulEndPage)

The tests described above focus on testing the back-end logic of your
PsyNet experiment. They catch errors to do with the instantiation of pages,
the running of code blocks, the growing of networks, and so on.
They do not catch logic to do with the front-end display of your
experiment. Writing such tests is more complicated, and we haven't
provided a tutorial for this yet; however, if you are interested in writing
your own such tests, please have a look at corresponding tests in the
PsyNet soure code, for example ``test_demo_timeline.py`` and
``test_demo_static.py``.
