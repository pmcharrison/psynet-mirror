============
The timeline
============

The timeline determines the sequential logic of the experiment.
A timeline comprises a series of *events* that are ordinarily
presented sequentially. There are three main kinds of events:

* `Pages`_
* `Page makers`_
* `Code blocks`_

`Pages`_ define the web page that is shown to the participant at a given
point in time, and have fixed content that is the same for all participants.
`Page makers`_ are like pages, but include content that is computed
when the participant's web page loads.
`Code blocks`_ contain server logic that is executed in between pages,
for example to assign the participant to a group or to save the participant's data.

All these events are defined as ``psynet`` classes inheriting from
`Event`, the generic event object.
Pages correspond to the `Page` class;
page makers correspond to the `PageMaker` class;
code blocks correspond to the `CodeBlock` class.
These different events may be created using their constructor functions, e.g.:

::

    from psynet.timeline import CodeBlock

    CodeBlock(lambda participant, experiment: participant.var.score = 50)


Pages
-----

Pages are defined in a hierarchy of object-oriented classes. The base class
is `Page`, which provides the most general and verbose way to specify a ``psynet`` page.
A simpler example is `InfoPage`, which takes a piece of text or HTML and displays it to the user:

::

    from psynet.page import InfoPage

    InfoPage("Welcome to the experiment!")

More complex pages might solicit a response from the user,
for example in the form of a text-input field:

::

    from psynet.modular_page import ModularPage, TextControl
    from psynet.page import Prompt

    ModularPage(
        "full_name",
        "Please enter your full name",
        control=TextControl(one_line=False),
        time_estimate=5,
    )

or in a multiple-choice format:

::

    from psynet.page import Prompt
    from psynet.modular_page import ModularPage, PushButtonControl

    ModularPage(
        "chocolate",
        Prompt("Do you like chocolate?"),
        control=PushButtonControl(["Yes", "No"]),
        time_estimate=3,
    )

See the documentation of individual classes for more guidance, for example:

* :class:`~psynet.timeline.Page`
* :class:`~psynet.page.InfoPage`
* :class:`~psynet.modular_page.ModularPage`
* :class:`~psynet.page.SuccessfulEndPage`
* :class:`~psynet.page.UnsuccessfulEndPage`.

:class:`~psynet.page.SuccessfulEndPage` and
:class:`~psynet.page.UnsuccessfulEndPage`
are special page types
used to complete a timeline; upon reaching one of these pages, the experiment will
terminate and the participant will receive their payment. The difference
between
:class:`~psynet.page.SuccessfulEndPage` and
:class:`~psynet.page.UnsuccessfulEndPage` is twofold:
in the former case, the participant will be marked in the database
with ``complete=True`` and ``failed=False``,
whereas in the latter case the participant will be marked
with ``complete=False`` and ``failed=True``.
In both cases the participant will be paid the amount that they have accumulated so far;
however, :class:`~psynet.page.UnsuccessfulEndPage` is typically used to terminate an experiment early,
when the participant has yet to accumulate much payment.

:class:`~psynet.page.UnityPage` allows for the integration of Unity and PsyNet. See the special section on :doc:`/experimenter/unity_integration` for more detailed information.

We hope to significantly extend the control types available in ``psynet`` in the future.
When you've found a custom control type useful for your own experiment,
you might consider submitting it to the ``psynet`` code base via
a Pull Request (or, in GitLab terminology, a Merge Request).

Consent pages
~~~~~~~~~~~~~

Before the start of an experiment you normally want to have the participant consent to the data collection
being carried out. We include the `Page` types :class:`~psynet.consent.MainConsent`,
:class:`~psynet.consent.DatabaseConsent`, :class:`~psynet.consent.AudiovisualConsent`,
:class:`~psynet.consent.OpenScienceConsent`, and :class:`~psynet.consent.VoluntaryWithNoCompensationConsent` for
experiments making use of recruitment systems, like `MTurk` and `Prolific`. Additionally, `Page`
types :class:`~psynet.consent.CAPRecruiterStandardConsentPage` and
:class:`~psynet.consent.CAPRecruiterAudiovisualConsentPage` make use of the CAP-Recruiter web application as the
recruitment instrument, respectively. One or more consent pages can be added to the start of an experiment timeline, as
appropriate.

This should be enough to start experimenting with different kinds of page types.
For a full understanding of the customisation possibilities, see the full :ref:`Page` and :ref:`ModularPage`
documentation.

Page makers
-----------

Ordinary pages in the timeline have fixed content that is shared between all participants.
Often, however, we want to present content that depends on the state of the current participant.
This is the purpose of page makers.
A page maker is defined by a function that is called when the participant accesses the page.
For example, a simple page maker might look like the following:

::

    from psynet.timeline import PageMaker

    PageMaker(
        lambda participant, experiment: InfoPage(f"You answered {participant.answer}.),
        time_estimate=5
    )

This example used a lambda function, which is a useful way of specifying inline functions
without having to give them a name.
This lambda function may accept up to two arguments, ``participant`` and ``experiment``,
but it doesn't have to accept all of these arguments. For example, the following is also valid:

::

    from psynet.timeline import PageMaker

    PageMaker(
        lambda participant: InfoPage(f"You answered {participant.answer}.),
        time_estimate=5
    )

See :class:`~psynet.timeline.PageMaker` documentation for more details.

Code blocks
-----------

Code blocks define code that is executed in between pages. They are defined in a similar
way to page makers, except they don't return an output. For example:

::

    from psynet.timeline import CodeBlock

    CodeBlock(
        lambda participant: participant.var.set("score", 10)
    )

See :class:`~psynet.timeline.CodeBlock` documentation for more details.

Control logic
-------------

Most experiments require some kind of non-trivial control logic,
such as conditional branches and loops. ``psynet`` provides
the following control constructs for this purpose:

* :func:`~psynet.timeline.conditional`
* :func:`~psynet.timeline.switch`
* :func:`~psynet.timeline.while_loop`

Note that these constructs are functions, not classes:
when called, they resolve to a sequence of events
that performs the desired logic.

Time estimate
-------------

It is considered good practice to pay online participants a fee that corresponds
approximately to a reasonable hourly wage, for example 9 USD/hour.
The ``psynet`` package provides sophisticated functionality for applying such
payment schemes without rewarding participants to participate slowly.
When designing an experiment, the researcher must specify along with each
page a ``time_estimate`` argument, corresponding to the estimated time in seconds
that a participant should take to complete that portion of the experiment.
This ``time_estimate`` argument is used to construct a progress bar displaying
the participant's progress through the experiment and to determine the participant's
final payment.


Combining events
----------------

The ``Experiment`` class expects us to provide an object of
class :class:`psynet.timeline.Timeline` in the ``timeline`` slot.
This ``Timeline`` object expects either events or lists of events
as its input; it will concatenate them together into one big list.
Following this method, here's a complete definition of a simple experiment:

::

    import psynet.experiment

    from psynet.modular_page import ModularPage, TextControl
    from psynet.page import InfoPage, Prompt, SuccessfulEndPage
    from psynet.timeline import PageMaker, Timeline

    class CustomExp(psynet.experiment.Experiment):
        timeline = Timeline(
            InfoPage(
                "Welcome to the experiment!",
                time_estimate=5
            ),
            PageMaker(
                lambda experiment, participant:
                    InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
                time_estimate=5
            ),
            ModularPage(
                "message",
                Prompt("Write me a message!"),
                control=TextControl(one_line=False),
                time_estimate=5,
            ),
            SuccessfulEndPage()
        )

It is generally wise to build up the test logic in small pieces. For example:

::

    from psynet.modular_page import ModularPage, TextControl
    from psynet.page import InfoPage, Prompt, SuccessfulEndPage
    from psynet.timeline import PageMaker, Timeline, join

    intro = join(
        InfoPage(
            "Welcome to the experiment!",
            time_estimate=5
        ),
        PageMaker(
            lambda experiment, participant:
                InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
            time_estimate=5
        )
    )

    test = ModularPage(
        "message",
        Prompt("Write me a message!"),
        control=TextControl(one_line=False),
        time_estimate=5,
    )

    timeline = Timeline(intro, test, SuccessfulEndPage())

Here we used the :func:`psynet.timeline.join` function to join
two events into a list (more than two events can also be joined).
When its arguments are all events, the ``join`` function behaves like a Python list constructor;
when the arguments also include lists of events, the ``join`` function
merges these lists. This makes it helpful for combining timeline logic,
where different bits of logic often correspond either to events or
lists of events.
