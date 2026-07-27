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
You can choose whether to include assets and whether to download a full PsyNet export
or only the database snapshot.

Exports use *identifier separation*: ``database.zip`` contains pseudonymous participant
identifiers so the archive remains loadable, while original recruiter identifiers are
written beside it in ``participant_identifiers.csv``. This is not anonymization of assets,
free text, logs, or experiment-defined basic data.

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
A typical export directory looks like this:

.. code-block:: text

    export/
    ├── database.zip
    ├── participant_identifiers.csv
    ├── lucid_entrant_identifiers.csv   # Lucid experiments only
    ├── manifest.json
    ├── basic_data.json OR basic_data/  # optional
    ├── assets/                         # optional
    ├── source_code.zip                 # optional
    └── logs.jsonl                      # SSH exports when available

If you want to choose your own export location, use the ``--path`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --path ~/Documents/my-experiment-data

By default the export command downloads **collected** assets: managed files
deposited during this deployment (for example participant recordings).
This can slow down data export if you have many files. You can disable this
behavior using the ``--assets`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --assets none

Use ``--assets all`` to also include pre-existing assets (cached stimuli,
external URLs) and to materialize on-demand assets. Treat exported media as
potentially identifying.

By default the export command will also try to export the experiment's source code.
If you experience an error during source code exporting, we recommend using the ``--no-source`` argument:

.. code:: bash

    psynet export ssh --app my-app-name --no-source

The ``--legacy`` argument processes the export locally instead of downloading from the
dashboard (which also saves a backup). This can be useful if you encounter troubles with
the default export method:

.. code:: bash

    psynet export ssh --app my-app-name --legacy


Identifier separation
=====================

``database.zip`` replaces direct recruiter identifiers with pseudonyms so that database
constraints remain satisfied and the archive can be loaded with ``psynet load``.
Original identifiers are available in ``participant_identifiers.csv``, keyed by
``participant_id``. Lucid experiments also write ``lucid_entrant_identifiers.csv``.

PsyNet does not inspect assets, free-text answers, logs, serialized variables, or
experiment-defined basic data for identifying content. Treat those as potentially
identifying unless you have scrubbed them yourself.

Assets
======

By default (``--assets collected``), only managed assets deposited during the
course of the experiment are exported — for example audio recordings.
Pre-existing assets such as ``CachedAsset`` stimuli and ``ExternalAsset`` URLs
are omitted, and on-demand assets are not generated.

Use ``--assets all`` for a fuller archive that also includes those pre-existing
assets and materializes on-demand outputs. Use ``--assets none`` to skip asset
files entirely.

Export data types
=================

Several types of data can be exported during the export process. They each have different functions.

The **database snapshot** is a portable copy of the physical database tables at a given time
(``database.zip`` plus identifier sidecars and ``manifest.json``).
It is useful for restoring experiments from a specific state and for analysis that reads
table CSVs directly.

The **basic data files** are a minimal set of data files that provide the essential information for downstream analysis.
They are only present if the experimenter has implemented the ``get_basic_data`` method in their experiment class.

The **assets** correspond to heavy files (e.g. audio, video) that are associated with the experiment.
Not all experiments use assets.

The **server logs** can also be exported when exporting from an SSH server.
These come in the form of a ``logs.jsonl`` file. Don't share these publicly
as they may contain confidential information.

A 'PsyNet full export' combines together all of the above types of data.
This is the default export type.

Analysing database.zip
======================

PsyNet provides helpers for reading the canonical snapshot without reconstructing an
older class-based CSV layout:

.. code:: python

    from psynet.export import (
        load_export_table,
        merge_participant_identifiers,
        unpack_json_column,
    )

    trials = load_export_table("database.zip", "trial")
    trials = unpack_json_column(trials, "definition", prefix="definition_")
    participants = load_export_table("database.zip", "participant")
    participants = merge_participant_identifiers(
        participants.rename(columns={"id": "participant_id"}),
        "participant_identifiers.csv",
    )

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
        import pandas as pd

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

PsyNet does not automatically anonymize or otherwise reinterpret experiment-defined
basic data. If you need to omit identifiers from a public release of basic data, do
that explicitly in your ``get_basic_data`` implementation.

Accessing basic data via the dashboard
--------------------------------------

You can preview the basic data in the dashboard by clicking on the 'Basic data' tab.


Accessing basic data via HTTP
------------------------------

Once you have implemented the ``get_basic_data`` method, you can access your basic data via an HTTP endpoint at ``/basic_data``.
This allows you to fetch data directly from a running experiment without needing to export it first.

The endpoint requires dashboard credentials, which can be provided as query parameters:
``dashboard_user`` and ``dashboard_password``.

You can construct the full URL using the ``basic_data_url`` property:

.. code:: python

    from psynet.experiment import Experiment

    url = Experiment.basic_data_url()
    # Returns: https://your-experiment-url.com/basic_data?dashboard_user=...&dashboard_password=...

Alternatively, you can access the endpoint directly by including the credentials in the URL:

.. code:: bash

    curl "https://your-experiment-url.com/basic_data?dashboard_user=USER&dashboard_password=PASSWORD"

Any GET parameters you pass to the endpoint will be forwarded to your ``get_basic_data`` method via the ``**kwargs`` parameter.
This allows you to implement dynamic behavior based on URL parameters.
For example, you could filter data by a specific parameter:

.. code:: python

    @classmethod
    def get_basic_data(cls, context=None, **kwargs):
        sheet = kwargs.get("sheet", "participant")
        # Return different data based on the 'sheet' parameter
        if sheet == "participant":
            return [...]
        elif sheet == "trial":
            return [...]

The endpoint returns JSON data directly, making it easy to consume from various tools:

- **Python**: Use ``requests.get(url).json()`` or ``urllib.request.urlopen(url).read()``
- **R**: Use ``jsonlite::fromJSON(url)``
- **Web browser**: Simply navigate to the URL to view the JSON data

Note that the endpoint should not expose sensitive information, as the authentication credentials are included in the URL itself.

Automatic backups
=================

PsyNet does have some functionality implemented for making regular data backups.
However, at the time of writing, this is disabled by default and should be considered experimental.
To enable it, you can set the ``automatic_backups`` class attribute to ``True`` in your experiment class.
