=================
Classes in PsyNet
=================

Introduction to object-orientation
----------------------------------

PsyNet is an *object-oriented* framework. Object-oriented programming is a popular pattern in Python and many other
programming languages. In object-oriented programming, one defines a collection of *classes*, where a class defines
an abstract category of objects, for example 'users', 'transactions', or 'events'. The programmer then creates and
manipulates instances of these classes, called *objects*. In Python, one can create classes as follows:

::

    class Person:
        def __init__(self, forename, surname):
            self.forename = forename
            self.surname = surname

        def greet(self):
            raise NotImplementedError


    class EnglishPerson(Person):
        def greet(self):
            print("Hi!")


    class FrenchPerson(Person)
        def greet(self):
            print("Salut!")


Here we created a base class called ``Person``, and two subclasses called ``EnglishPerson`` and ``FrenchPerson``.
Subclasses inherit the structure of their parent class, but also can have additional custom logic.
Here the ``EnglishPerson`` and ``FrenchPerson`` subclasses share the parent concept of forenames and surnames,
but they have customized greeting methods corresponding to their respective languages.

We can then create instances of these classes as follows:

::

        jeff = EnglishPerson(forename="Jeff", surname="Stevens")
        madeleine = FrenchPerson(forename="Madeleine", surname="de la Coeur")

        print(jeff.surname)  # yields "Stevens"

        jeff.greet()  # yields "Hi!"
        madeleine.greet()  # yields "Salut!"


Working with PsyNet requires fluency in object-oriented programming in Python.
You should aim to be familiar with the following concepts:

- Defining classes
- Defining subclasses
- Defining methods
- Using the ``@property`` decorator
- Using ``super()``
- Creating instances
- Class attributes versus instance attributes

If some of these concepts are new to you, we recommend doing a few relevant online tutorials before proceeding.

PsyNet classes in experiment.py
-------------------------------

If you open a given PsyNet experiment (e.g. ``demos/mcmcp/experiment.py``) you will typically see a variety of
PsyNet classes. These will be imported from particular PsyNet modules, for example:

::

    from psynet.page import InfoPage


Page classes like ``InfoPage`` are particularly important for defining the experiment's timeline;
you'll see logic for instructions using this class, for example.

Many PsyNet experiments also include some custom subclasses that inherit from particular PsyNet classes.
For example, you might see something like this:

::

    from psynet.trial.mcmcp import MCMCPTrial

    class CustomTrial(MCMCPTrial):
        def show_trial(self, ...):
            ...

This allows the experimenter to define a particular kind of trial for their experiment, that inherits certain
functionality from core PsyNet (e.g. the logic of a Markov Chain Monte Carlo with People [MCMCP] experiment)
but also adds custom logic (e.g. displaying a particular kind of stimulus to the participant).

In the next section we'll introduce the core PsyNet classes in proper detail so that you understand how
they all fit together and how they are used in practice.


Overview of key PsyNet classes
------------------------------

Experiment
^^^^^^^^^^

The ``Experiment`` class is the most central class in the PsyNet experiment.
It is defined in ``experiment.py``, the main Python file in your experiment directory.
You define your ``Experiment`` class by subclassing PsyNet's built-in
:class:`~psynet.experiment.Experiment` class. Your custom ``Experiment`` class
must include a definition of the experiment's timeline:

::

    import psynet.experiment

    class Exp(psynet.experiment.Experiment):
        timeline = join(
            InfoPage(...)
            ...
        )
    )

The ``timeline`` attribute should receive a series of ``Elt`` objects (see below),
with these Elts joined together using the :func:`~psynet.timeline.join` function.

There are various other customizations that can be applied to the experiment via this experiment class,
see the :class:`~psynet.experiment.Experiment` documentation for details.

Participant
^^^^^^^^^^^

The :class:`~psynet.participant.Participant` class is used to represent participants.
Each Participant object has various attributes that are populated during the experiment,
carrying useful information for identifying the participant and recording their experience
during the experiment. For example, ``Participant.id`` gives a unique integer ID for the Participant;
``Participant.creation_time`` tells you when the Participant started the experiment;
``Participant.failed`` tells you if the Participant has been failed, and so on.
For a full list of attributes see the :class:`~psynet.participant.Participant` class documentation.

Most PsyNet experimenters do not interact much with built-in Participant attributes.
Instead, they define custom Participant variables which are used to track state during the experiment.
Participant variables are defined via ``Participant.var``, and can take any name, for example
``Participant.var.custom_variable``. For example, one might write
``print(participant.var.custom_variable)`` to print the current value of ``custom_variable``,
or write ``participant.var.custom_variable = 3`` to set ``custom_variable`` to 3.
For setting Participant variables in lambda functions (see below),
Python syntax doesn't allow you to write expressions like ``participant.var.custom_variable = 3`` directly;
instead we write ``participant.var.set("custom_variable", 3)``.

Elt
^^^

:class:`~psynet.timeline.Elt` objects define the logic of the experiment.
They determine what materials are shown to the participant, how the participant responds to
those materials, how the server processes those responses, and so on.

There are several main types of :class:`~psynet.timeline.Elt` objects:

- :class:`psynet.timeline.Page` objects determine the web pages that are presented to the participant;
- :class:`psynet.timeline.PageMaker` objects generate Pages on-demand;
- :class:`psynet.timeline.CodeBlock` objects define code that runs in between Pages;
- Control flow functions determine how these elements are sequenced within the timeline.

We will now introduce each of these concepts in a little more detail.
See their dedicated documentation for full information.

Page
""""

:class:`psynet.timeline.Page` objects determine the web pages that are presented to the participant.
The base :class:`psynet.timeline.Page` class allows you to define a Page using a custom Jinja template.
Jinja is a templating engine that is popular for creating websites with a Python back-end.
For example, here's what the template for :class:`psynet.timeline.SuccessfulEndPage` currently
looks like:

::

    {% extends "timeline-page.html" %}

    {% block main_body %}
        That's the end of the experiment!
        {% if experiment.var.show_bonus %}
            {% include "final-page-bonuses.html" %}
        {% endif %}
        Thank you for taking part.

        <p class="vspace"></p>
        <p>
            Please click "Finish" to complete the HIT.
        </p>
        <p class="vspace"></p>

        <button type="button" id="next-button" class="btn btn-primary btn-lg" onClick="dallinger.submitAssignment();">Finish</button>
    {% endblock %}

Most PsyNet users don't work with these Jinja templates directly. Instead, they use PsyNet helper classes
that create these templates programmatically.

The simplest case is the :class:`~psynet.page.InfoPage`. The Info Page simply displays some information to
the participant, and does not request any response. An Info Page can be created like this:

::

    from psynet.page import InfoPage

    InfoPage("Welcome to the experiment!", time_estimate=5)

The ``time_estimate`` parameter tells PsyNet how many seconds the participant is expected to spend
on the page. This is a common feature of PsyNet Pages. This time estimate is used to manage
the progress bar and to compensate participants pro rata for their time on the experiment.

More often than not, experimenters eventually end up using the :class:`~psynet.modular_page.ModularPage`
class for their experiment implementations. The Modular Page is a powerful way of defining pages
that combines two basic elements: the :class:`~psynet.modular_page.Prompt` and the
:class:`~psynet.modular_page.Control`. The Prompt defines what is presented to the participant,
whereas the Control defines their interface for responding. The PsyNet library contains many
built-in implementations of Prompts and Controls, but it's perfectly possible to create your own
Prompts or Controls for a given experiment, and then reuse them in future experiment implementations.

Here's an example of a Modular Page which combines an :class:`~psynet.modular_page.AudioPrompt`
with a :class:`~psynet.modular_page.PushButtonControl`:

::

    from psynet.modular_page import ModularPage, AudioPrompt, PushButtonControl

    ModularPage(
        "question_page",
        AudioPrompt("https://my-server.org/stimuli/audio.wav", "Do you like this audio file?"),
        PushButtonControl(["Yes", "No"]),
        time_estimate=self.time_estimate,
    )

The other important kind of page is the :class:`~psynet.page.EndPage`. An EndPage is used to mark
the end of an experiment. There are two commonly used types of End Pages, triggering different
end-of-experiment behavior:
the :class:`~psynet.page.SuccessfulEndPage` and the :class:`~psynet.page.UnsuccessfulEndPage`.
The latter is typically used when the participant fails some kind of performance check
and is made to finish the experiment early.

Page Maker
"""""""""

:class:`psynet.timeline.PageMaker` objects generate Pages on-demand.
The resulting pages can be dynamic, incorporating content that depends on the current
state of the participant or the experiment.

::

    from psynet.timeline import PageMaker

    PageMaker(lambda participant: InfoPage(
        f"Welcome to the experiment, {participant.var.name}.",
        time_estimate=5
    ))

The Page Maker takes a function as its primary argument. Typically we use a lambda function,
which allows us to define the Page Maker content in-line. However, it's also possible
to pass a named function which is defined or imported earlier in the code.

The Page Maker function can optionally take a variety of arguments, of which ``participant``
is one. To find the full list of available arguments, see the documentation.

Warning: The Page Maker function will be called more than once for a given page,
including whenever the page is refreshed. It is important therefore that the code
is **idempotent**, i.e. calling it multiple times should have the same effect as calling
it just once. It is a bad idea to incorporate random functions in this code.

Code Block
"""""""""

:class:`psynet.timeline.CodeBlock` objects define code that runs in between Pages.
They are similar to Page Makers, but do not return pages. Like Page Makers,
they take a function as the primary argument, which can optionally take a variety of arguments
such as ``participant``.
Unlike Page Makers, they only ever run once, so they're a safe place to put random functions.

::

    from psynet.timeline import CodeBlock

    CodeBlock(lambda participant: participant.var.seed = random.randint(0, 5)


Control Flow
^^^^^^^^^^^

Control flow functions determine how these elements are sequenced within the timeline.
They are currently not implemented as classes, but rather as pure functions;
we might change this in the future though to achieve a cleaner syntax.

While Loop
""""""""""

A While Loop repeats a particular series of Elts while a particular condition is
satisfied. The condition is specified as a function that is called with various
optional arguments, most commonly ``participant``.

::

    while_loop(
        "example_loop",
        lambda participant: participant.answer == "Yes",
        Module(
            "loop",
            ModularPage(
                "loop_nafc",
                Prompt("Would you like to stay in this loop?"),
                control=PushButtonControl(["Yes", "No"], arrange_vertically=False),
                time_estimate=3,
            ),
        ),
        expected_repetitions=3,
    )


For Loop
""""""""

::

A For Loop instructs PsyNet to loop over the values of a list,
and using these values to dynamically generate Elts in the manner of a Page Maker.
The following example uses a For Loop to create a series of Info Pages
counting from 1 to 3:

::

    from psynet.timeline import for_loop
    from psynet.page import InfoPage

    for_loop(
        label="for_loop_1",
        iterate_over=lambda: [1, 2, 3],
        logic=lambda number: InfoPage(f"{number} / 3"),
        time_estimate_per_iteration=5,
    )

For Loops can also include random functions to generate their seed lists.
This provides a straightforward way to randomize the order of material
presented to Participants. For example:

::

    import random
    from psynet.timeline import for_loop
    from psynet.page import InfoPage

    for_loop(
        label="for_loop_2",
        iterate_over=lambda: random.sample(range(10), 3),
        logic=lambda number: InfoPage(f"Stimulus {number}"),
        time_estimate_per_iteration=5,
    )


Conditional
"""""""""""

A Conditional construct is used to branch Timeline logic according to whether or not
a given Condition is satisfied. The Condition is programmed as a function,
analogous to the function for the While Loop,
which should return either True or False.
If the function returns True, then the logic follows the first branch;
if it returns False, the logic follows the second branch (if such a branch
was specified). For example:

::

    from psynet.timelime import conditional
    from psynet.page import InfoPage

    conditional(
        "like_chocolate",
        lambda participant: participant.answer == "Yes",
        InfoPage("It's nice to hear that you like chocolate!", time_estimate=5),
        InfoPage(
            "I'm sorry to hear that you don't like chocolate...",
            time_estimate=3,
        ),
    )

Switch
""""""

A Switch construct is a more powerful version of the Conditional construct
that supports arbitrary numbers of branches. As before, the experimenter
writes a function that is evaluated once the Participant reaches the Switch,
but this time the function can return an arbitrary Python object
(technically, this object must be 'hashable', which includes things like
strings, integers, and floats).
The experimenter then also provides a dictionary of branches,
where each branch is a piece of Timeline logic,
and the branches are keyed by possible outputs of the function.
PsyNet sends the Participant to the branch that's keyed by the output
of the function. For example:

::

    from psynet.timeline import switch

    switch(
        "color",
        lambda participant: participant.answer,
        branches={
            "Red": InfoPage("You selected 'red'.", time_estimate=1),
            "Green": InfoPage("You selected 'green'.", time_estimate=1),
            "Blue": InfoPage("You selected 'blue'.", time_estimate=1),
        },
    )

Module
^^^^^^

A :class:`~psynet.timeline.Module` is a construct for organizing Timeline logic
into standalone blocks. For example, if we create a pre-screening test that involves
asking the Participant some spelling questions, we might make this pre-screening test a Module
and then distribute it in a helper package.

Modules are useful for tracking the Participants' journey through the experiment.
For example, the Dashboard contains a useful visualization that shows how many Participants
have started and finished each Module.

Modules are also useful for encapsulating Participant state. This means that variables don't
unintentionally leak from one part of the Experiment to the other, something which otherwise
can produce subtle bugs. To take advantage of this feature, the experimenter avoids setting
participant variables in this way (which sets variables that are 'global' to the entire timeline):

::

    participant.var.custom_variable = 3

and instead sets participant variables this way:

::

    participant.locals.custom_variable = 3

or equivalently:

::

    participant.module_state.var.custom_variable = 3

Modules can be used as the base class for object-oriented hierarchies of Timeline constructs.
For example, the :class:`~psynet.trial.main.TrialMaker` class is a special kind of Module class
that implements logic for administering Trials to the participant (see below).
One day we might similarly create a PreScreen class for implementing pre-screening tests.

Modules are also useful for managing Assets, as described below.

Asset
^^^^^

An :class:`~psynet.asset.Asset` is some kind of file (or collection of files) that
is referenced during an experiment. These might for example be video files that we play
to the participant, or perhaps audio recordings that we collect from the participant.

The API for Assets is powerful but complex. PsyNet provides many patterns for creating Assets
and for accessing them within an experiment. These are documented in detail in the
Assets chapter. For now, we will just illustrate the simplest of these patterns,
which is to define an Asset at the Module level.

You can create an asset within a Module by passing it to the Module constructor's
``assets`` argument. This argument expects a dictionary. For example:

::

    import psynet.experiment
    from psynet.asset import CachedAsset

    class Exp(psynet.experiment.Experiment):
        timeline = join(
            Module(
                "my_module",
                my_pages(),
                assets={
                    "logo": CachedAsset("logo.svg"),
                }
            )
        )

You can then access this asset within your module as follows:

::

    from psynet.timeline import PageMaker

    def my_pages():
        return PageMaker(
            lambda assets: ModularPage(
                "audio_player",
                ImagePrompt(assets["logo"], "Look at this image."),
                time_estimate=5,
            )
        )

Note how the asset must be accessed within a ``PageMaker``,
and is pulled from the optional ``assets`` argument that we included
in the lambda function. This ``assets`` argument is populated with a dictionary
of assets from the current module.


Trial
^^^^^

The :class:`~psynet.trial.main.Trial` class represents a single Trial within the Experiment.
A Trial typically involves administering some kind of stimulus to the Participant
and recording their response.

The PsyNet experimenter typically creates their own Trial subclass as part of the
Experiment implementation.

TODO

Node
^^^^

Trial maker
^^^^^^^^^^^

Creating your own

Connection to SQLAlchemy classes
--------------------------------



Connection to Dallinger classes
-------------------------------
