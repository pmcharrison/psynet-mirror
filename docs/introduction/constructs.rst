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

- Experiment
- Page (also modular page, control, prompt)
- Asset
- Module
- Trial
- Node
- Trial maker

Creating your own

Connection to SQLAlchemy classes
--------------------------------



Connection to Dallinger classes
-------------------------------
