.. _data:
.. highlight:: shell

====
Data
====

In PsyNet, we categorize data into three main forms:

- **Basic data**: Data provided via the the ``/basic_data`` endpoint. This includes only information relevant to downstream analysis and must be implemented explicitly by the experimenter.
- **Database snapshot**: A raw copy of the database at a given time, useful for restoring experiments from a specific state.
- **PsyNet full export**: A complete export of data from an experiment, intended for offline analysis or sharing.


Basic data: The /basic_data endpoint
====================================

The ``/basic_data`` endpoint serves processed experiment data.
To use it, implement the ``get_basic_data`` method in your experiment class.
We recommend that the method returns a dictionary, where the keys correspond to object types,
and the values are lists of dictionaries, where each dictionary contains the fields you want to expose.

You can customize this method to meet your needs — for example,
by using query parameters to expose different data “sheets” (e.g. ``/basic_data?sheet=participant``).

Here is an example implementation:

.. code:: python

    class Exp(psynet.experiment.Experiment):
        # Your experiment configuration here
        # ...

        @classmethod
        def get_basic_data(cls, context=None, **kwargs, ):
            data = {
                "trial":
                    [
                    # List all trials with their answers
                        {
                            "id": trial.id,
                            "answer": str(trial.answer),
                        }
                        for trial in Trial.query.filter_by(failed=False, finalized=True).all()
                    ],
                "participant": [
                    # List all participants with their last answer
                    {
                        "id": participant.id,
                        "answer": str(participant.answer),
                    }
                    for participant in Participant.query.filter_by().all()
                ],
            }
            sheet = kwargs.get("sheet", "participant")
            if sheet not in data:
                raise DataError("Invalid sheet parameter")
            return data[sheet]

Database snapshot
=================

PsyNet automatically creates database snapshots at regular intervals (typically once per minute) while your experiment is running.
These snapshots act as a safety net against data loss and allow you to restore the experiment state if needed.

PsyNet full export
==================

You can export data from PsyNet either via the command line or through the experiment dashboard.

If you export from the dashboard, also your psynet export is automatically backed up and you will be notified via Slack
if you have set up the `Slack integration <../tutorials/setting_up_slack.html>`_.

Exporting from the dashboard
----------------------------

Visit the “Export” section (endpoint: ``/dashboard/export``).
Choose whether to anonymize participant data and whether to include assets (e.g., audio files). You can export:

- A full PsyNet export (processed data and optionally including assets)
- A database snapshot (excluding assets)

Exporting from the command line
-------------------------------

Use the ``psynet export`` command to export data from local, SSH, or Heroku-based experiments:

.. code:: bash

    psynet export local
    psynet export ssh --app my-app-name
    psynet export heroku --app my-app-name

.. note::

    Prepend ``docker/`` to these commands if you are running PsyNet within Docker.


The data is saved by default to ``~/psyNet-data/export``.
The organization of exports and the naming of the files is still under discussion and development.
If you want to choose your own export location, use the ``--path`` argument:

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

Even when you use the command line to export data, it tries to export the data in the same way as the dashboard does (and thus also save a backup of the export).
If you want to only download the database snapshot and automatically process it locally, you can use the ``--legacy`` argument:

**Anonymization**.
Data can be exported in anonymous or non-anonymous mode. Anonymous mode strips
worker IDs from the participants table and excludes assets that are marked
as personal, for example audio recordings. This is good for producing datasets
that you want to upload to open-access repositories.

**Logs**.
When exporting from an ``ssh`` server, the server logs will be exported as a ``logs.jsonl`` file.
This file contains structured JSON log entries with timestamps, log levels, and messages that can be easily parsed and analyzed.
You can open this file with a text editor to investigate what happened during the experiment.
It's normally best to keep these logs private though, as it's easy to imagine confidential information
accidentally being leaked via such logs.

**Database snapshot vs basic data**.
Data is by defaulted exported in both database snapshot and basic data form.
The database snapshot corresponds to the exact way in which the data is stored
in the database when the experiment is live. This format is required if you
want to resurrect an experiment from a snapshot.
The basic data form is more suited to downstream data analysis; it unpacks some
of the data formats and merges certain information between tables.
