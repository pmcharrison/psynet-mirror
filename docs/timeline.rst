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

All these events are defined as ``dlgr_utils`` classes inheriting from
`Event`, the generic event object.
Pages correspond to the `Page` class;
page makers correspond to the `PageMaker` class;
code blocks correspond to the `CodeBlock` class.
These different events may be created using their constructor functions, e.g.:

::

    from dlgr_utils.timeline import CodeBlock

    CodeBlock(lambda participant, experiment: participant.var.score = 50)


Pages
-----

Pages are defined in a hierarchy of object-oriented classes. The base class 
is `Page`, which provides the most general and verbose way to specify a ``dlgr_utils`` page.
A simpler example is `InfoPage`, which takes a piece of text or HTML and displays it to the user:

::

    from dlgr_utils.timeline import InfoPage

    InfoPage("Welcome to the experiment!")

More complex pages might solicit a response from the user,
for example in the form of a text-input field:

::

    from dlgr_utils.timeline import TextInputPage

    TextInputPage(
        "full_name",
        "Please enter your full name",
        time_estimate=5,
        one_line=True
    )

or in a multiple-choice format:

::

    from dlgr_utils.timeline import NAFCPage

    NAFCPage(
        label="chocolate",
        prompt="Do you like chocolate?",
        choices=["Yes", "No"],
        time_estimate=3
    )

See the documentation of individual classes for more guidance, for example:

* :ref:`Page`
* :ref:`InfoPage`
* :ref:`TextInputPage`
* :ref:`NumberInputPage`
* :ref:`NAFCPage`
* :ref:`SuccessfulEndPage`
* :ref:`UnsuccessfulEndPage`.

``SuccessfulEndPage`` and ``UnsuccessfulEndPage`` are special page types
used to complete a timeline; upon reaching one of these pages, the experiment will
terminate and the participant will receive their payment. The difference
between ``SuccessfulEndPage`` and ``UnsuccessfulEndPage`` is twofold:
in the former case, the participant will be marked in the database 
with ``complete=True`` and ``failed=False``,
whereas in the latter case the participant will be marked
with ``complete=False`` and ``failed=True``.
In both cases the participant will be paid the amount that they have accumulated so far;
however, ``UnsuccessfulEndPage`` is typically used to terminate an experiment early,
when the participant has yet to accumulate much payment.

Often you may wish to create a custom page type. The best way is usually
to start with the source code for a related page type from the ``dlgr_utils``
package, and modify it to make your new page type. These page types
should usually inherit from the most specific relevant ``dlgr_utils`` page type;
for example, `NumberInputPage` inherits from `TextInputPage`, 
and adds a validation step to make sure that the user has entered a valid number.

We hope to significantly extend the page types available in ``dlgr_utils`` in the future.
When you've found a custom page type useful for your own experiment,
you might consider submitting it to the ``dlgr_utils`` code base via 
a Pull Request (or, in GitLab terminology, a Merge Request).

This should be enough to start experimenting with different kinds of page types.
For a full understanding of the customisation possibilities, see the full :ref:`Page` documentation.

Page makers
-----------

Ordinary pages in the timeline have fixed content that is shared between all participants.
Often, however, we want to present content that depends on the state of the current participant.
This is the purpose of page makers.
A page maker is defined by a function that is called when the participant access the page.
For example, a simple page maker might look like the following:

::

    from dlgr_utils.timeline import PageMaker

    PageMaker(
        lambda participant, experiment: InfoPage(f"You answered {participant.answer}.),
        time_estimate=5
    )

This example used a lambda function, which is a useful way of specifying inline functions
without having to give them a name.
This lambda function may accept up to two arguments, ``participant`` and ``experiment``,
but it doesn't have to accept all of these arguments. For example, the following is also valid:

::

    from dlgr_utils.timeline import PageMaker

    PageMaker(
        lambda participant: InfoPage(f"You answered {participant.answer}.),
        time_estimate=5
    )

See :ref:`PageMaker` documentation for more details.

Code blocks
-----------

Code blocks define code that is executed in between pages. They are defined in a similar
way to page makers, except they don't return an input. For example:

::

    from dlgr_utils.timeline import CodeBlock

    CodeBlock(
        lambda participant: participant.var.set("score", 10)
    )

See :ref:`CodeBlock` documentation for more details.

Control logic
-------------

Most experiments require some kind of non-trivial control logic, 
such as conditional branches and loops. ``dlgr_utils`` provides
the following control constructs for this purpose:

* :ref:`conditional`
* :ref:`switch`
* :ref:`while_loop`

Note that these constructs are functions, not classes:
when called, they resolve to a sequence of events
that performs the desired logic.

Time estimate
-------------

It is considered good practice to pay online participants a fee that corresponds
approximately to a reasonable hourly wage, for example 9 USD/hour.
The ``dlgr_utils`` package provides sophisticated functionality for applying such 
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
class :class:`dlgr_utils.timeline.Timeline` in the ``timeline`` slot.
This ``Timeline`` object expects either events or lists of events
as its input; it will concatenate them together into one big list.
Following this method, here's a complete definition of a simple experiment:

::

    import dlgr_utils.experiment

    from dlgr_utils.timeline import (
        InfoPage,
        PageMaker,
        TextInputPage,
        SuccessfulEndPage,
        Timeline
    )

    class CustomExp(dlgr_utils.Experiment):
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
            TextInputPage(
                "message",
                "Write me a message!",
                time_estimate=5,
                one_line=False
            ),
            SuccessfulEndPage()
        )

    extra_routes = CustomExp().extra_routes()

It is generally wise to build up the test logic in small pieces. For example:

::
    
    from dlgr_utils.timeline import (
        InfoPage,
        PageMaker,
        TextInputPage,
        SuccessfulEndPage,
        Timeline,
        join
    )

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

    test = TextInputPage(
                "message",
                "Write me a message!",
                time_estimate=5,
                one_line=False
            )

    timeline = Timeline(intro, test)

Here we used the :func:`dlgr_utils.timeline.join` function to join
two events into a list. When its arguments are all events,
the ``join`` function behaves like a Python list constructor;
when the arguments also include lists of events, the ``join`` function
merges these lists. This makes it handy for combining timeline logic,
where different bits of logic often correspond either to events or 
lists of events.