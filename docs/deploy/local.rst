Local deployments
=================

Use a local deployment when collecting data on a computer in a laboratory or
in the field. Unlike disposable local debugging, every local deployment has a
required ID:

.. code-block:: bash

    psynet deploy local --id gibbs

The ID contains lowercase letters, digits, and dashes. It is scoped to the
experiment directory and identifies a history of database snapshots under
``data/snapshots/<id>/``.

Managed local snapshots currently support the standard and ``--legacy`` local
runners, but not ``--docker``.

Snapshots
---------

PsyNet creates a database snapshot every ten minutes while the experiment is
running and another after a normal shutdown. Snapshots are private,
non-anonymized recovery files for resuming on the same machine. They do not
include assets or replace a full :ref:`data export <data>`.

Running the same command again displays the ten most recent snapshots and asks
which one to resume. The latest is selected by default. Scripts can bypass the
prompt:

.. code-block:: bash

    psynet deploy local --id gibbs --snapshot latest
    psynet deploy local --id gibbs --snapshot 4

Before resetting the shared local PostgreSQL database, PsyNet checks whether it
contains an interrupted managed deployment. If so, PsyNet saves a recovery
snapshot in the owning experiment directory. A failed recovery prevents the
new deployment from starting.

Databases created before this snapshot system have no managed ID. Adopt one
explicitly after checking that the current experiment directory contains the
matching source:

.. code-block:: bash

    psynet deploy local --id gibbs --adopt-existing

Deployment history
------------------

Deployment and snapshot events are appended to
``data/deployment-events.jsonl``. Successful exports and remote deployment or
destruction commands run from the experiment directory use the same history.
Add an operator comment with:

.. code-block:: bash

    psynet comment --id gibbs "Changed headphones."

The ``--id`` option can be omitted when the current experiment owns the local
database. Event history and snapshots may contain operational or participant
information and are excluded by PsyNet's standard ``.gitignore``.
