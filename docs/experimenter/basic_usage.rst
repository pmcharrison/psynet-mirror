===========
Basic usage
===========

Once installed (see 'Installation' section), you can import ``psynet`` like any other Python package:

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

Alternatively, you can use a *deploy token* by simply copying the already prepared deploy token

``qgwAvbx7C8J59CtiswKp``

of the user with username *cap* and include it as follows:

::

    git+https://cap:qgwAvbx7C8J59CtiswKp@gitlab.com/computational-audition-lab/psynet#egg=psynet

*\*In case you want to use a different deploy token, please consult the section on* :ref:`Deploy tokens` *for how to generate those.*

The above line will always deploy the most recent commit in the `master` branch. But there exist also several ways for specifying a different particular version of ``psynet`` when deploying an experiment. This can be e.g. a *version tag*, a *branch name*, or a *commit hash*. We recommend specifying a particular Git commit hash like ``000b14389171a9f0d7d713466b32bc649b0bed8e`` in the case you want to be sure your experiment always deploys with the same version of ``psynet`` even if the package subsequently changes. You can find this ``<commit_hash>`` in GitLab or similar. For example:

::

    git+https://cap:qgwAvbx7C8J59CtiswKp@gitlab.com/computational-audition-lab/psynet@<commit_hash>#egg=psynet

In the same way you can use a Git version tag ``<tag>`` like ``v1.5.0`` to always deploy a certain tagged commit:

::

    git+https://cap:qgwAvbx7C8J59CtiswKp@gitlab.com/computational-audition-lab/psynet@<tag>#egg=psynet

Contrary to the above, use a branch name ``<branch_name>`` like ``dev`` in case you want to deploy an experiment always using the most recent commit in a certain Git branch:

::

    git+https://cap:qgwAvbx7C8J59CtiswKp@gitlab.com/computational-audition-lab/psynet@<branch_name>#egg=psynet

Custom packages
---------------

When using a custom package in a Dallinger/PsyNet experiment, you also need to include it in your experiment’s ``requirements.txt``. You can use a package by including the following in your requirements:

.. code-block:: console

  -e git+<link_to_repository>@<commit_hash_or_branch_name>#egg=<package_name>

For example,

.. code-block:: console

  -e git+https://gitlab.com/computational-audition-lab/theory-rep-samp/vowels@v1.5.1#egg=vowel_extract

If the repository is a private repository, you will need to generate a custom deploy token. Follow the process described in :ref:`Deploy tokens` and based on the above example replace ``username`` and ``deploy_token`` in the line below accordingly.

.. code-block:: console

  -e git+https://<username>:<deploy_token>@gitlab.com/computational-audition-lab/theory-rep-samp/vowels@v1.5.1#egg=vowel_extract

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

    from psynet.modular_page import ModularPage, TextControl
    from psynet.page import InfoPage, Prompt, SuccessfulEndPage
    from psynet.timeline import PageMaker, Timeline


    class CustomExp(psynet.Experiment):
        timeline = Timeline(
            InfoPage(
                "Welcome to the experiment!",
                time_estimate=5,
            ),
            PageMaker(
                lambda experiment, participant:
                    InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
                time_estimate=5,
            ),
            ModularPage(
                "message",
                Prompt("Write me a message!"),
                control=TextControl(one_line=False),
                time_estimate=5,
            ),
            SuccessfulEndPage()
        )

    extra_routes = CustomExp().extra_routes()

The elements of the timeline are presented in sequence to form the logic of the experiment.

Conclusion
----------

Those are the key elements to get started with the ``psynet`` package!
For a more detailed tutorial, continue to :doc:`timeline`.
