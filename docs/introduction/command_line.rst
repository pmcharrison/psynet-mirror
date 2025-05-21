.. _command_line:

============
Command line
============

Once you have installed PsyNet, you interact with it by running commands in your Unix shell.
Generally speaking, you should execute all of these commands within your experiment directory
(e.g. if you are running the timeline demo: ``psynet/demos/timeline``).

The commands take slightly different forms depending on how you have installed PsyNet.
If you are running PsyNet via Docker, you run commands that look like this:

.. code:: bash

    bash docker/psynet debug local

If you are running PsyNet within a virtual environment, you omit the ``bash docker/`` and
just write commands like this:

.. code:: bash

    psynet debug local


.. _debug:

Run an experiment in debug mode (``debug``)
-------------------------------------------

The following code runs an experiment in debug mode on your local computer:

.. code:: bash

    psynet debug local

The following code runs an experiment in debug mode on your own web server, via SSH;
this will push the experiment code to Heroku, but won't recruit any participants,
even if your recruiter is set to ``mturk`` or ``prolific``.
Note the specification of an app name.

.. code:: bash

    psynet debug ssh --app my-app-name

This code does the same, but provisioning the web server automatically via the paid service Heroku:

.. code:: bash

    psynet debug heroku --app my-app-name


.. _deploy:

Deploy an experiment (``deploy``)
---------------------------------

This command deploys an experiment, and enable the recruiter so you can collect real data.

.. code:: bash

    psynet deploy ssh --app my-app-name  # for deploying via SSH
    psynet deploy heroku --app my-app-name  # for deploying via Heroku

(Experimental): It is possible to deploy an experiment that resurrects the state of a previous
experiment deployment. To do this you add ``--archive path/to/database.zip`` where
``path/to/database.zip`` is the path to the ``database.zip`` file created by a previous PsyNet export.


.. _estimate:

Estimate maximum reward and completion time (``estimate``)
----------------------------------------------------------

This command examines the timeline, estimates how long the participant will take to complete the experiment,
and how much they need to be paid as a result.

.. code:: bash

    psynet estimate

.. warning::

    This functionality is still experimental and is known to produce inaccurate results
    in certain cases. Always check these estimates manually before finalizing an experiment implementation.


.. _export:

Export data from an experiment (``export``)
-------------------------------------------

This command export data from an experiment. The data is saved by default to ``~/PsyNet-data/export``.

.. code:: bash

    psynet export local
    psynet export ssh --app my-app-name
    psynet export heroku --app my-app-name

To see further options for the export command (e.g. if you want to control the export of assets),
append ``--help`` to these commands:

.. code:: bash

    psynet export local --help
    psynet export ssh --help
    psynet export heroku --help

For more information on PsyNet data export see `Exporting <../deploy/export.html>`_.


.. _generate_constraints:


Generate the constraints.txt file (``generate-constraints``)
------------------------------------------------------------

This command generates a constraints.txt file in the experiment directory stating the exact versions of Python
packages that will be installed when the server is deployed. The role of this command is still
under discussion at the moment, so don't worry too much about it.

.. code:: bash

  psynet generate-constraints


Run the experiment's regression test
------------------------------------

This command runs the experiment's regression test, as defined in ``test.py``. This normally involves
running one or more simulated participants through the experiment.

.. code:: bash

  psynet test


Simulate data for an experiment
-------------------------------

This command generates simulated data for an experiment by running the experiment's regression test
and exporting the resulting data.

.. code:: bash

  psynet simulate


.. _update:

Update PsyNet/Dallinger (``update``)
------------------------------------

.. note::

    The following command only applies if you have installed PsyNet in a local
    environment, rather than using Docker.

This command updates the local installations of `PsyNet` and `Dallinger` to their latest versions.
While the default is to update both packages, they can also be set to specific
versions (e.g. downgraded) using the ``--psynet-version`` and
``--dallinger-version`` command line options.

.. code:: bash

  psynet update

**Usage**

.. code:: bash

  psynet update [OPTIONS]

  Options:
    --dallinger-version TEXT  The git branch, commit or tag of the Dallinger
                              version to install.
    --psynet-version TEXT     The git branch, commit or tag of the psynet
                              version to install.
    --verbose                 Verbose mode
    --help                    Show this message and exit.
