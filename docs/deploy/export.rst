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
and development. However, there are already a couple of important principles that
are worth sharing:

**Anonymization**.
Data can be exported in anonymous or non-anonymous mode. Anonymous mode strips
worker IDs from the participants table and excludes assets that are marked
as personal, for example audio recordings. This is good for producing datasets
that you want to upload to open-access repositories.

**Database vs processed data**.
Data is by defaulted exported in both database form and processed form.
The database form corresponds to the exact way in which the data is stored
in the database when the experiment is live. This format is required if you
want to resurrect an experiment from a snapshot.
The processed form is more suited to downstream data analysis; it unpacks some
of the data formats and merges certain information between tables.

Currently the data processing step can be slow for large databases. We are working
on this problem and plan to improve it significantly.
