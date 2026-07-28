.. _command_line:

============
Command line
============

Once you have installed PsyNet, you interact with it by running commands in your Unix shell.
Generally speaking, you should execute all of these commands within your experiment directory
(e.g. if you are running the timeline demo: ``PsyNet/demos/experiments/timeline``).

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

For more information on PsyNet data export see `Data <../deploy/data.html>`_.


.. _generate_constraints:


Generate the constraints.txt file (``generate-constraints``)
------------------------------------------------------------

This command generates a constraints.txt file in the experiment directory stating the exact versions of Python
packages that will be installed when the server is deployed. The role of this command is still
under discussion at the moment, so don't worry too much about it.

.. code:: bash

  psynet generate-constraints


Set up an experiment (``setup``)
--------------------------------

This command scaffolds missing experiment files, pins a bare ``psynet``
requirement to the active PsyNet installation, generates ``constraints.txt``,
synchronizes the constrained dependencies with ``uv``, and runs
``uv pip check``. Run it inside a dedicated active virtual environment:

.. code:: bash

  psynet setup

Synchronization removes packages that are not required by the experiment.
If PsyNet is installed editable, setup asks how to record it in
``requirements.txt``: keep the editable checkout, pin its current commit from
the checkout's ``origin`` remote (so forks work once the commit has been
pushed), or retain an existing explicit requirement. The same choice can be
supplied non-interactively with ``--psynet-source editable``, ``commit``, or
``existing``.

If the active virtual environment is PsyNet's shared checkout environment
(typically the repository ``.venv``), setup refuses to synchronize by default.
Interactively it explains the situation and offers a numeric menu: create a
dedicated ``.venv`` here (recommended default), cancel, prepare files only, or
install into the shared environment anyway; non-interactively use
``--prepare-only`` to scaffold and generate constraints without syncing, or
``--force-shared-env`` to sync anyway. ``--prepare-only`` also works in
dedicated experiment environments when you want to skip ``uv pip sync`` /
``uv pip check``.

PsyNet's own monorepo CI uses ``psynet scripts scaffold --skip-constraints``
because in-repo demos and test experiments share the repository's development
environment. Local ``debug`` and ``test`` commands recognize those directories
and prepare their ignored boilerplate automatically. Running ``psynet setup``
there performs only this lightweight preparation and does not rewrite
requirements or synchronize the shared environment. See :ref:`scripts` for the
standalone ``scaffold`` / ``update`` / ``prune`` commands.


.. _scripts:

Manage experiment boilerplate (``scripts``)
-------------------------------------------

The ``psynet scripts`` group manages standard experiment boilerplate
(Dockerfile, ``docker/`` helpers, ``pytest.ini``, ``test.py``, and related
templates) without synchronizing a virtual environment. Use these when you want
file-level control; prefer ``psynet setup`` when creating a dedicated constrained
environment for a standalone experiment.

Inspect the available subcommands with:

.. code:: bash

  psynet scripts --help

``scaffold``
~~~~~~~~~~~~

Create any missing PsyNet boilerplate files in the current experiment directory.
If ``experiment.py`` or ``requirements.txt`` are missing, starter versions are
created as well. Existing authored files are left alone.

.. code:: bash

  psynet scripts scaffold

By default, standalone experiments also pin a bare ``psynet`` requirement and
generate ``constraints.txt`` when needed. Pass ``--skip-constraints`` to skip
pinning and constraint generation (in-repo demos and test experiments do this
automatically):

.. code:: bash

  psynet scripts scaffold --skip-constraints

``update``
~~~~~~~~~~

Overwrite scaffold-managed boilerplate with the latest templates from the
installed PsyNet version. Existing ``config.txt`` and ``README.md`` files are
preserved because authors commonly customize them.

.. code:: bash

  psynet scripts update

``psynet update-scripts`` remains as a deprecated alias for this command.

``prune``
~~~~~~~~~

Remove scaffold-managed boilerplate from the experiment directory, leaving
authored files such as ``experiment.py`` and ``requirements.txt``. ``README.md``
is always preserved. Paths that differ from the current PsyNet templates,
including customized ``config.txt`` files, are preserved by default;
``--force`` removes those paths without checking their contents.

.. code:: bash

  psynet scripts prune
  psynet scripts prune --force


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


.. _install:

Install PsyNet components (``install``)
---------------------------------------

Install additional PsyNet components and utilities.

.. _install_autocomplete:

Install shell completion (``install autocomplete``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This command installs shell tab completion for the ``psynet`` command. It automatically
detects your shell and adds the appropriate completion setup to your shell configuration file.

.. code:: bash

  psynet install autocomplete

This is equivalent to running the ``./install-completion.sh`` script manually from the root directory
of an editable PsyNet installation. For more information about shell completion, see :ref:`shell_completion`.

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
