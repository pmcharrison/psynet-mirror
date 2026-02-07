.. _data:
.. highlight:: shell

====
Data
====

When an experiment is live, data is stored in a PostgreSQL database.
The data can be inspected in real time via the experiment dashboard,
or it can be exported for offline analysis.

Viewing data in the dashboard
=============================

The 'database' section of the dashboard provides a simple viewer of database objects.
Each object type is displayed in a separate table.
It is possible to perform certain actions on selected objects, such as marking them as 'failed'.

Exporting data from the dashboard
=================================

The 'export' section of the dashboard allows you to export data from the database.
It is possible to customize the nature of the export in various ways,
for example concerning anonymization and the inclusion of assets.

Exporting data from the command line
====================================

It is also possible to export data from the command line using the 'psynet export' command.
This should normally be run in the experiment directory for the experiment you are running,
using a virtual environment with the same dependencies as the deployed experiment.

.. code:: bash

    psynet export local
    psynet export ssh --app my-app-name
    psynet export heroku --app my-app-name

The data is saved by default to ``~/psynet-data/export``.
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

The ``--legacy`` argument uses an older export method that only downloads the database snapshot
and processes it locally, rather than using the dashboard export method (which also saves a backup).
This can be useful if you encounter troubles with the default export method:

.. code:: bash

    psynet export ssh --app my-app-name --legacy


Anonymization
=============

When anonymization is selected, certain personally identifying columns are removed from the exported data.
By default, this means removing the 'worker_id' column from the participants table.
Depending on your experiment design, you may want to anonymize other columns as well.

Assets
======

By default, only assets that are created during the course of the experiment are exported.
This might for example include audio recordings.
However, it is also possible to export all assets, including for example experiment stimuli.

Export data types
=================

Several types of data can be exported during the export process. They each have different functions.

The **database snapshot** is a raw copy of the database at a given time.
It is useful for restoring experiments from a specific state;
however, it is less human-readable than some of the other export types.

The **data files** are created by reorganizing and reformatting the database snapshot,
grouping data by object type, unpacking JSON columns into separate columns, etc.
They are typically a similar size to the database snapshot.

The **basic data files** are a minimal set of data files that provide the essential information for downstream analysis.
They are only present if the experimenter has implemented the ``get_basic_data`` method in their experiment class.

The **assets** correspond to heavy files (e.g. audio, video) that are associated with the experiment.
Not all experiments use assets.

The **server logs** can also be exported when exporting from an ``ssh`` server.
These come in the form of a ``logs.jsonl`` file. Don't share these publicly
as they may contain confidential information.

A 'PsyNet full export' combines together all of the above types of data.
This is the default export type.

More about basic data
=====================

The basic data route is really intended for confident experimenters.
If you are not comfortable with SQLAlchemy, you may want to stick to the default export methods.

You define the basic data representation for your experiment by implementing the ``get_basic_data`` method
in your experiment class. You have a lot of flexibility in how you implement this method.

JSON method
-----------

One possibility is to return an arbitrary dictionary of data.
In this case, the data will be saved as a JSON file.
For example:

.. code:: python

    @classmethod
    def get_basic_data(cls, context=None, **kwargs):
        return {
            "trials": [
                {
                    "id": trial.id,
                    "question": trial.definition.get("question"),
                    "answer": trial.answer,
                }
                for trial in Trial.query.all()
            ]
        }

DataFrame method
----------------

Alternatively, you can return a dictionary of dataframes.
In this case, the data will be saved as a set of CSV files.
For example:

.. code:: python

    @classmethod
    def get_basic_data(cls, context=None, **kwargs):
        trials = [
            {
                "id": trial.id,
                "participant_id": trial.participant_id,
                "animal": trial.definition.get("animal"),
                "block": trial.block,
                "answer": trial.answer,
                "score": trial.score,
            }
            for trial in StaticTrial.query.all()
        ]
        participants = [
            {
                "id": participant.id,
                "status": participant.status,
                "bonus": participant.bonus,
            }
            for participant in Participant.query.all()
        ]
        return {
            "trial": pd.DataFrame.from_records(trials),
            "participant": pd.DataFrame.from_records(participants),
        }

Anonymization in basic data
-----------------------------

When exporting data, PsyNet calls ``get_basic_data()`` with an ``anonymize`` keyword argument
(``True`` or ``False``) indicating whether anonymized data should be returned.
You can use this parameter to conditionally exclude or modify sensitive information in your basic data.

For example, you might exclude participant IDs or other personally identifying information when ``anonymize=True``:

.. code:: python

    @classmethod
    def get_basic_data(cls, context=None, anonymize=False, **kwargs):
        trials = [
            {
                "id": trial.id,
                "participant_id": trial.participant_id if not anonymize else None,
                "animal": trial.definition.get("animal"),
                "answer": trial.answer,
            }
            for trial in StaticTrial.query.all()
        ]
        return {
            "trial": pd.DataFrame.from_records(trials),
        }

Automatic backups
=================

PsyNet does have some functionality implemented for making regular data backups.
However, at the time of writing, this is disabled by default and should be considered experimental.
To enable it, you can set the ``automatic_backups`` class attribute to ``True`` in your experiment class.
