===========
Basic usage
===========

Once installed (see :doc:`installation`), you can import ``psynet`` like any other Python package:

::

    import psynet

When you deploy the experiment to Heroku, you will also need to specify the package in ``requirements.txt``.
This can be done by adding the following line:

::

    git+ssh://git@gitlab.com/computational-audition-lab/psynet

You can also modify this line to specify a particular version to install,
and to provide authentication to the repository if required;
see `this documentation <https://dallinger.readthedocs.io/en/latest/private_repo.html>`_
for details.
In particular, to add your GitLab password, you can do something like this:

::

    git+https://<username>:<password>@gitlab.com/computational-audition-lab/psynet#egg=psynet

Alternatively, you can create a personal access token (PAT) for your GitLab account 
with read-only permissions and include it as follows:

::

    git+https://<pat>@gitlab.com/computational-audition-lab/psynet#egg=psynet

When deploying an experiment, we recommend specifying a particular Git commit in 
this line, for example:

::

    git+https://<pat>@gitlab.com/computational-audition-lab/psynet@<commit_hash>#egg=psynet

where ``<commit_hash>`` looks something like ``000b14389171a9f0d7d713466b32bc649b0bed8e``
(you can find this in GitLab or similar).
This makes sure your experiment always deploys with the same version of ``psynet``,
even if the package subsequently changes.

Like any other Dallinger experiment, an experiment implementation requires an `experiment.py` file
in your main directory, as well as a `static` folder and a `templates` folder. 
We plan to release a cookiecutter template to create these files for you, 
so you can begin by just editing the template.
The instructions below describe some differences between a traditional experiment 
and an experiment using ``psynet``.

The experiment class
--------------------

In normal Dallinger experiments, `experiment.py` must define a class that is an immediate descendant
of the `Experiment` class, for example:

::
    
    import dallinger.experiment

    class CustomExp(dallinger.experiment.Experiment):
        ...

The same applies in ``psynet``, except we provide a custom `Experiment` class.
You can use it as follows:

::

    import psynet.experiment

    class CustomExp(psynet.Experiment):
        ...


You might think of doing it this way instead: 

::

    from psynet.experiment import Experiment

    class CustomExp(Experiment):
        ...

but for some reason this can elicit subtle bugs that will
probably interfere with your experiment.
Let us know if you work out what the problem is and how to fix it.

The participant class
---------------------

``psynet`` also defines an extension of the Dallinger ``Participant`` class
that has some additional useful features. When referring to the ``Participant``
class in your experiment, make sure you've imported the class from ``psynet``.

::

    from psynet.participant import Participant

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

The key difference between ``psynet`` and core Dallinger is that
``psynet`` introduces the *timeline*, a useful abstraction for 
defining the control logic of experiments. 
The timeline is defined by overriding the `timeline` attribute
of the Experiment class, for example:

::

    import psynet.experiment

    from psynet.timeline import (
        PageMaker,
        TextInputPage,
        Timeline
    )
    from psynet.page import (
        InfoPage,
        SuccessfulEndPage
    )

    class CustomExp(psynet.Experiment):
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

The elements of the timeline are presented in sequence to form the logic of the experiment.

Conclusion
----------

Those are the key elements to get started with the ``psynet`` package!
For a more detailed tutorial, continue to :doc:`timeline`.
