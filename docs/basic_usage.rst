===========
Basic usage
===========

Once installed (see :doc:`installation`), you can import ``dlgr_utils`` like any other Python package:

::

    import dlgr_utils

When you deploy the experiment to Heroku, you will also need to specify the package in ``requirements.txt``.
This can be done by adding the following line:

::

    git+ssh://git@gitlab.com/computational-audition-lab/dlgr-utils

You can also modify this line to specify a particular version to install,
and to provide authentication to the repository if required;
see `this documentation <http://docs.dallinger.io/en/latest/private_repo.html>`_
for details.
In particular, to add your GitLab password, you can do something like this:

::

    git+https://<username>:<password>@gitlab.com/computational-audition-lab/dlgr-utils#egg=dlgr_utils

Alternatively, you can create a personal access token (PAT) for your GitLab account 
with read-only permissions and include it as follows:

::

    git+https://<pat>@gitlab.com/computational-audition-lab/dlgr-utils#egg=dlgr_utils

When deploying an experiment, we recommend specifying a particular Git commit in 
this line, for example:

::

    git+https://<pat>@gitlab.com/computational-audition-lab/dlgr-utils@<commit_hash>#egg=dlgr_utils

where ``<commit_hash>`` looks something like ``000b14389171a9f0d7d713466b32bc649b0bed8e``
(you can find this in GitLab or similar).
This makes sure your experiment always deploys with the same version of ``dlgr_utils``,
even if the package subsequently changes.

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
        PageMaker,
        TextInputPage,
        Timeline
    )
    from dlgr_utils.page import (
        InfoPage,
        SuccessfulEndPage
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

The elements of the timeline are presented in sequence to form the logic of the experiment.

Conclusion
----------

Those are the key elements to get started with the ``dlgr_utils`` package!
For a more detailed tutorial, continue to :doc:`timeline`.
