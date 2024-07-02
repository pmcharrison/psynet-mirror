.. _export:
.. highlight:: shell

=========
Exporting
=========

We export data from PsyNet experiments using the command line.
Choose the appropriate command depending on whether you want to export data
from a local experiment, an SSH server, or Heroku.

.. code:: bash

    psynet export local
    psynet export ssh --app my-app-name
    psynet export heroku --app my-app-name

.. note::

    Prepend ``docker/`` to these commands if you are running PsyNet within Docker.


The data is saved by default to ``~/PsyNet-data/export``.
The organization of exports and the naming of the files is still under discussion
and development. If you want to choose your own export location, use the ``--path`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --path ~/Documents/my-experiment-data

By default the export command will download assets that were generated during the course of the experiment.
This can slow down data export if you have many files. You can disable this behavior using the ``--assets`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --assets none

By default the export command will also try to export the experiment's source code. 
This feature was causing some problems in PsyNet v11.7; if you experience an error
during source code exporting, we recommend using the ``--no-source`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --no-source

**Anonymization**.
Data can be exported in anonymous or non-anonymous mode. Anonymous mode strips
worker IDs from the participants table and excludes assets that are marked
as personal, for example audio recordings. This is good for producing datasets
that you want to upload to open-access repositories.

**Logs**.
When exporting from an ``ssh`` server the server logs will also be exported as a ``.log`` file.
You can open this with a text editor to investigate what happened in a given experiment.
It's normally best to keep these logs private though, as it's easy to imagine confidential information
accidentally being leaked via such logs.

**Database vs processed data**.
Data is by defaulted exported in both database form and processed form.
The database form corresponds to the exact way in which the data is stored
in the database when the experiment is live. This format is required if you
want to resurrect an experiment from a snapshot.
The processed form is more suited to downstream data analysis; it unpacks some
of the data formats and merges certain information between tables.
