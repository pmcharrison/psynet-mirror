===========
Basic usage
===========

Once installed (see :doc:`installation`), you can import ``dlgr_utils`` like any other Python package:

::

    import dlgr_utils

Like any other Dallinger experiment, an experiment implementation requires an `experiment.py` file
in your main directory, as well as a `static` folder and a `templates` folder. 
We plan to release a cookiecutter template to create these files for you, 
so you can begin by just editing the template.
The instructions below describe some differences between a traditional experiment 
and an experiment using ``dlgr_utils``.

The experiment class
--------------------

In normal Dallinger experiments, `experiment.py` must define a class that is an immediate descendant
of the `Experiment` class, for example:

::
    
    import dallinger.experiment

    class CustomExp(dallinger.experiment.Experiment):
        ...

The same applies in ``dlgr_utils``, except we provide a custom `Experiment` class.
You can use it as follows:

::

    import dlgr_utils.experiment

    class CustomExp(dlgr_utils.Experiment):
        ...


You might think of doing it this way instead: 

::

    from dlgr_utils.experiment import Experiment

    class CustomExp(Experiment):
        ...

but for some reason this can elicit subtle bugs that will
probably interfere with your experiment.
Let us know if you work out what the problem is and how to fix it.

The participant class
---------------------

``dlgr_utils`` also defines an extension of the Dallinger ``Participant`` class
that has some additional useful features. When referring to the ``Participant``
class in your experiment, make sure you've imported the class from ``dlgr_utils``.

::

    from dlgr_utils.participant import Participant

Exposing the routes
-------------------

Somewhere after the definition of your custom Experiment class,
you must include the following line of code:

::

    extra_routes = CustomExp().extra_routes()

We will eventually petition the Dallinger team to modify the source
such that this line becomes unnecessary.

Building the timeline
---------------------

The key difference between ``dlgr_utils`` and core Dallinger is that
``dlgr_utils`` introduces the *timeline*, a useful abstraction for 
defining the control logic of experiments. 
The timeline is defined by overriding the `timeline` attribute
of the Experiment class, for example:

::

    import dlgr_utils.experiment

    from dlgr_utils.timeline import (
        InfoPage,
        ReactivePage,
        TextInputPage,
        SuccessfulEndPage
    )

    class CustomExp(dlgr_utils.Experiment):
        timeline = Timeline(
            InfoPage(
                "Welcome to the experiment!",
                time_allotted=5
            ),
            ReactivePage(            
                lambda experiment, participant: 
                    InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
                time_allotted=5
            ),
            TextInputPage(
                "message",
                "Write me a message!",
                time_allotted=5,
                one_line=False
            ),
            SuccessfulEndPage()
        )

    extra_routes = CustomExp().extra_routes()

The elements of the timeline are presented in sequence to form the logic of the experiment.

Conclusion
----------

Those are the key elements to get started with the ``dlgr_utils`` package!
For a more detailed tutorial, continue to :doc:`timeline`.
