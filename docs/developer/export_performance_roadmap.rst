.. _export_performance_roadmap:

==========================
Export performance roadmap
==========================

.. note::

    This is a planning document. It records the intended target architecture and
    implementation sequence; it does not describe the behavior of the current
    PsyNet release.

Purpose
-------

PsyNet exports currently combine several expensive operations:

* Dallinger creates a PostgreSQL ``COPY`` snapshot.
* PsyNet loads every database row through SQLAlchemy, converts each ORM object
  with ``to_dict()``, and writes a second set of class-based CSV files.
* Assets are exported one at a time, using one database query and one storage
  operation per asset.
* Regular and anonymized exports repeat much of the same work.
* The dashboard compresses the resulting directory, including media that is
  usually already compressed.

The new design will make the database snapshot the primary data
representation, use one content-addressed representation for managed assets,
and make command-line asset exports incremental.

Measured baseline
=================

The following measurements were collected on a database containing 1,000
participants, 30,000 trials, and 142,008 rows in total:

.. list-table::
   :header-rows: 1

   * - Operation
     - Time
   * - Current ORM-based PsyNet CSV export
     - 14.19 seconds
   * - PostgreSQL ``COPY`` plus a pandas reconstruction of the old format
     - 1.47 seconds
   * - Raw PostgreSQL ``COPY``
     - 0.17 seconds

Approximately 93% of the ORM export time was spent constructing ORM objects
and decoding or re-encoding serialized fields, rather than writing CSV.
Removing only the redundant serialization work was projected to improve the
export by about 1.4 times; avoiding ORM object construction altogether improved
it by about 9.7 times.

Asset transfer showed a larger difference. For 300 small assets over SSH with a
30 ms round-trip time:

.. list-table::
   :header-rows: 1

   * - Operation
     - Time
   * - One Paramiko ``sftp.get`` call per asset
     - 57.83 seconds
   * - Cold ``rsync`` transfer
     - 2.28 seconds
   * - Repeat ``rsync`` transfer
     - 0.78 seconds

For 300 MB of incompressible media, ZIP deflation took 5.25 seconds and reduced
the output by only 0.03%; storing the files without deflation took 0.32 seconds.

Agreed design decisions
=======================

This roadmap makes the following breaking design choices:

* The old class-based CSV directory (for example ``Bot.csv`` and
  ``CustomTrial.csv``) will be removed rather than retained as a compatibility
  format.
* Existing deployments and old ``database.zip`` archives will not be migrated.
  The changes will apply to newly created deployments.
* :class:`~psynet.trial.main.Trial` will become an independent PsyNet database
  model backed by the physical table ``trial``. It will no longer subclass
  Dallinger's ``Info`` model.
* Dallinger's ``info`` table will remain available for genuine Dallinger
  ``Info`` objects. Trial rows will not be stored there.
* ``database.zip`` will remain the canonical database snapshot. Its member
  files will use physical database table names, including ``trial.csv``.
* Experiment-defined basic data will remain optional. PsyNet will not invent a
  default basic-data representation.
* The ``--anonymize yes|no|both`` model will be replaced by one export with a
  separate ``participant_identifiers.csv`` file.
* Selected assets will all be exported, irrespective of the current
  ``personal`` flag. PsyNet will not claim that recordings, free text, logs, or
  experiment-defined basic data are anonymous.
* Managed assets will have one content-addressed filesystem representation
  shared by remote storage, the local cache, and exports.
* Live asset URLs will use permanent random access tokens initially. URL expiry
  is explicitly deferred.
* Command-line exports will use a persistent local asset cache. Dashboard
  downloads will remain complete, nonincremental archives.

Target export layout
====================

The planned output is:

.. code-block:: text

    export/
    ├── database.zip
    ├── participant_identifiers.csv
    ├── source_code.zip
    ├── manifest.json
    ├── assets/
    │   ├── manifest.csv
    │   └── objects/
    │       └── sha256/
    │           └── <content-hash>
    ├── basic_data/              # optional, experiment-defined
    ├── basic_data.json          # optional alternative
    └── logs.jsonl               # when available

The exact database snapshot consists of ``database.zip`` together with
``participant_identifiers.csv``. The database archive contains pseudonymous
participant identifiers and can be loaded independently for analysis or
redeployment. The identifier file supplies the original recruiter identifiers
when those are needed.

The top-level manifest will describe the snapshot identity, creation time,
deployment ID, PsyNet and Dallinger versions, table row counts, and checksums.
It will not attempt to certify the export as anonymous.

Database snapshot
=================

Fast table export
-----------------

The database export will use one PostgreSQL ``COPY`` pass and will no longer
load the complete database through the ORM. This removes:

* ``_prepare_db_export`` and its full-table ORM hydration;
* the per-object ``_db_instance_to_dict`` pass;
* class-based output grouping;
* pandas construction solely for recreating the old CSV representation; and
* duplicate regular and anonymous database exports.

The archive will remain a ZIP so that all tables form one portable snapshot and
``psynet load`` can treat it atomically. ZIP members such as nested ZIP files
and compressed media will not be deflated a second time.

Independent Trial model
-----------------------

``Trial`` will become a registered PsyNet root model, conceptually:

.. code-block:: python

    @register_table
    class Trial(SQLBase, SQLMixin, AssetParentMixin):
        __tablename__ = "trial"

Custom trial classes will continue to use single-table polymorphism within the
``trial`` table.

The model will explicitly define the fields it currently obtains from
``Info`` and still needs, including network linkage and completion state.
Redundant Dallinger concepts such as ``origin_id`` and ``contents`` will not be
copied unless a concrete use is identified.

This change also requires:

* changing PsyNet foreign keys from ``info.id`` to ``trial.id``;
* changing the ``TrialNetwork.participants`` join to use ``trial``;
* registering ``trial`` in database export and archive ingestion order;
* updating participant, asset, process, and error relationships;
* making dashboard network monitoring query trials rather than infos;
* replacing the create-and-rate dependency on Dallinger ``Transformation``
  with a PsyNet-native trial relationship; and
* replacing remaining ``node.infos`` assumptions with trial relationships.

Participant identifiers
-----------------------

The live ``Participant`` table remains the sole source of participant
identifiers because recruiters need these values while an experiment is
running. Other tables will reference participants by ``participant_id`` rather
than copying identifiers.

The initial cleanup includes:

* removing ``ErrorRecord.worker_id`` and deriving it through
  ``error.participant`` when needed;
* removing ``Response.client_ip_address`` and using the participant's current
  address when needed;
* replacing relationships keyed by ``worker_id`` with relationships keyed by
  ``participant_id`` where practical; and
* auditing PsyNet models for other duplicated worker, assignment, HIT, IP, or
  recruiter identifiers.

Removing per-response IP storage intentionally gives up the history of IP
changes during a participant session.

During export, direct participant identifiers will be copied to
``participant_identifiers.csv``, keyed by ``participant_id``. The corresponding
columns in ``database.zip`` will contain valid pseudonymous placeholders so
that database constraints remain satisfied and the archive remains loadable.
The exact field set will be defined centrally and will include standard
recruiter identifiers and PsyNet-specific direct identifiers.

This is identifier separation, not anonymization. Assets, free-text answers,
logs, serialized experiment variables, and basic data are not inspected for
identifying content.

Analysis utilities
------------------

PsyNet will provide small utilities for consuming the canonical snapshot
without rebuilding the old export format:

* ``load_export_table(database_zip, table)`` will read a physical table directly
  from the archive.
* ``unpack_json_column(data_frame, column, ...)`` will explicitly unpack a
  selected JSON column, with configurable prefixes and collision handling.
* A participant-identifier merge utility will restore original identifier
  columns when explicitly requested.

JSON unpacking will use ordinary JSON parsing rather than reconstructing
arbitrary Python objects through jsonpickle. Nested dictionaries may be
normalized through pandas, but existing columns will never be silently
overwritten.

Basic data
----------

``get_basic_data()`` remains an optional experiment hook. If it returns
``None``, no basic-data output is created. PsyNet will not automatically
anonymize, classify, or otherwise reinterpret experiment-defined basic data.

Asset architecture
==================

One object representation
-------------------------

Managed assets will be stored by immutable content identity:

.. code-block:: text

    objects/sha256/<content-hash>

Large directories may use a hash-named directory prefix containing their
original relative structure. The final design must preserve safe subfile access
without allowing path traversal.

An asset manifest will map semantic metadata to stored objects, including:

* asset ID;
* content hash and object path;
* extension and folder status;
* module, participant, trial, node, and network associations where applicable;
* local key and description; and
* storage backend information needed by export tooling.

The object path will be the same in local storage, SSH storage, S3 storage, the
local cache, and exported object directories. Human-readable directory trees
may be materialized by a separate convenience utility, but they are not the
canonical representation.

Content hashes provide integrity and deduplication, not access control. The
implementation will use SHA-256 rather than the current MD5 content identity.

Live access
-----------

The storage path will no longer contain an obfuscation suffix. Browser access
will instead use a permanent random token associated with the Asset row:

.. code-block:: text

    GET /asset/<access-token>/<optional-subpath>

The route will:

#. resolve the token to an Asset record;
#. obtain the content-addressed object path and storage backend;
#. validate folder subpaths;
#. reject missing or undeposited assets; and
#. ask the storage backend to serve the object.

The access token and content hash serve different purposes:

* the access token is an unguessable, revocable browser capability;
* the content hash identifies immutable bytes for storage and export.

Tokens will not initially expire. A leaked token therefore remains valid until
it is rotated or its Asset is deleted. This is approximately the current
security model, but it separates access capabilities from filesystem
organization.

Local storage may serve files with ``send_file`` or an internal web-server
redirect. Private S3 objects cannot be redirected through a permanent public
URL without reverting to path secrecy, so the first private-S3 implementation
may proxy responses through PsyNet. It must preserve HTTP range requests for
audio and video. Expiring S3 or CDN URLs remain a possible future optimization.

Persistent local cache
----------------------

Command-line exports will use a shared cache:

.. code-block:: text

    ~/psynet-data/cache/assets/
    └── objects/
        └── sha256/
            └── <content-hash>

The export process will:

#. download ``database.zip`` and the asset manifest;
#. determine the required content hashes;
#. compare them with the local cache;
#. fetch only missing objects;
#. verify each hash before atomically moving the object into the cache; and
#. hardlink cached objects into the timestamped export.

If the cache and export are on different filesystems, PsyNet will copy instead
of hardlinking. Hardlinked exports remain valid if the cache path is later
removed because each hardlink independently references the underlying inode.

Transport implementations will use:

* local hardlinks or copies for local deployments;
* ``rsync --files-from`` for SSH storage;
* concurrent missing-key downloads for S3;
* a batched HTTP fallback when direct backend access is unavailable; and
* existing download or generation behavior for external and on-demand assets.

Cache entries will be immutable. Partial downloads will use temporary names and
will never count as cache hits. Automatic eviction and garbage collection are
deferred; an initial implementation may provide only inspection and manual
pruning commands.

Dashboard exports
-----------------

Dashboard downloads remain nonincremental because an ordinary browser download
must transmit a complete archive. They will nevertheless avoid most current
overhead:

* no ORM-based second CSV representation;
* one identifier-separated database snapshot;
* no per-asset database query or rename step;
* direct reads from content-addressed objects; and
* no DEFLATE pass over already-compressed media.

Dashboard exports will therefore be bounded primarily by the number and total
size of selected assets. S3-backed dashboard exports still need to read every
selected object from S3 and send every byte to the browser.

Implementation sequence
=======================

Each phase should be delivered as a focused, independently reviewable change.
Later phases may refine APIs introduced earlier, but should not require the old
class-based export to remain available.

Phase 1: Regression benchmarks
------------------------------

* Add an export benchmark based on a reproducible populated experiment.
* Measure database snapshot time, asset preparation time, bytes transferred,
  cache-hit behavior, archive construction time, and peak memory.
* Keep a slow end-to-end benchmark for representative scale and a smaller
  merge-request regression benchmark.

Phase 2: Independent Trial table
--------------------------------

* Move Trial to a registered ``trial`` table.
* Replace all PsyNet ``info.id`` foreign keys and relationship assumptions.
* Replace the create-and-rate Transformation dependency.
* Update dashboard monitoring and database browsing.
* Update archive ingestion and database initialization.
* Remove obsolete Info compatibility code from PsyNet.

Phase 3: Identifier normalization
---------------------------------

* Remove identifier copies from ErrorRecord and Response.
* Convert identity-based foreign keys to participant-ID relationships.
* Audit remaining models for duplicate participant identifiers.
* Define the central set of Participant identifier fields.

Phase 4: Canonical database export
----------------------------------

* Remove the ORM/class-based CSV export.
* Produce ``database.zip`` directly with PostgreSQL ``COPY``.
* Extract original Participant identifiers into
  ``participant_identifiers.csv`` while writing pseudonymous values to the
  archive.
* Add snapshot metadata, row counts, and checksums.
* Remove anonymization modes and their command-line/dashboard controls.
* Add table loading, JSON unpacking, and identifier merge utilities.

Phase 5: Content-addressed asset storage
----------------------------------------

* Introduce SHA-256 object paths and an asset manifest.
* Replace ``host_path``/``export_path`` duality with one object path.
* Add permanent access tokens and the asset-serving route.
* Update local and S3 storage backends, including folder and range-request
  behavior.
* Retire URL/path obfuscation as a storage concern.

Phase 6: Incremental command-line export
----------------------------------------

* Add the persistent local object cache.
* Add local, SSH, S3, and HTTP synchronization implementations.
* Materialize exports with hardlinks where possible.
* Preserve existing asset-scope choices (``none``, experiment assets, or all
  assets), but do not filter selected assets by ``personal``.
* Add cache inspection and manual pruning.

Phase 7: Faster dashboard archives
----------------------------------

* Build archives directly from database and object storage.
* Use stored ZIP members for compressed media and nested archives.
* Remove temporary asset-copy trees where possible.
* Retain full-download semantics and artifact backup behavior.

Phase 8: Documentation and cleanup
----------------------------------

* Rewrite user-facing export and asset documentation for the new layout.
* Document the breaking archive boundary and the independent Trial model.
* Document identifier separation without describing the result as anonymous.
* Remove obsolete flags, legacy code, tests, and troubleshooting advice.

Acceptance criteria
===================

Database correctness
--------------------

* A fresh experiment uses ``trial`` as the physical Trial table.
* A database snapshot round-trips through ``psynet load`` with matching row
  counts and stored values, apart from intentionally separated identifiers.
* ``participant_identifiers.csv`` can restore original Participant identifier
  values through an explicit utility.
* No PsyNet table duplicates Participant worker IDs or client IP addresses.
* Custom tables are included in deterministic dependency order.

Database performance
--------------------

* Export time scales with database bytes rather than the number of ORM objects.
* The representative database benchmark is at least five times faster than the
  old ORM export.
* Peak memory no longer requires all ORM rows and their dictionary
  representations to coexist.
* Requesting one export does not produce two full database snapshots.

Asset correctness
-----------------

* Every selected managed asset appears in the manifest and resolves to an
  object with the expected SHA-256 digest.
* Two Assets with identical bytes can reference one object.
* Exported hardlinks remain readable after the cache entry is unlinked.
* Folder subpaths cannot escape their content-addressed object root.
* Live audio and video support HTTP range requests.
* Permanent access tokens are unguessable and can be rotated or revoked.

Asset performance
-----------------

* A repeat command-line export transfers no unchanged managed-asset bytes.
* SSH synchronization uses bounded connection setup rather than one round trip
  per asset.
* S3 synchronization downloads only missing content hashes.
* Dashboard archive creation does not copy every asset into a second temporary
  tree or deflate already-compressed media.

Breaking changes
================

This roadmap intentionally permits:

* removal of the old ``data/*.csv`` class export;
* removal of ``--legacy`` once the replacement is established;
* removal of ``--anonymize`` and dashboard anonymization choices;
* replacement of ``Info`` inheritance with an independent Trial model;
* replacement of ``info.csv`` trial data by ``trial.csv``;
* removal of ``ErrorRecord.worker_id`` and
  ``Response.client_ip_address``;
* changes to managed-asset paths and URLs;
* removal or reinterpretation of ``obfuscate`` and ``personal``; and
* inability to load exports created before the breaking release.

Non-goals
=========

The first implementation will not:

* migrate live deployments or old database archives;
* preserve the old class-based CSV format;
* guarantee that an export is anonymous;
* inspect arbitrary responses, assets, logs, or basic data for personal
  information;
* provide expiring asset URLs;
* automatically evict unused local cache objects;
* make browser downloads incremental; or
* preserve Dallinger ``Info`` transmission and transformation behavior for
  Trial objects.

Risks and mitigations
=====================

Central model change
--------------------

Removing ``Info`` as Trial's base affects a central model and may expose obscure
dependencies on Dallinger relationships. The implementation must exercise
static, chain, Gibbs, and create-and-rate experiments, as well as failure
propagation and dashboard monitoring.

Identity completeness
---------------------

Recruiters and custom tables may introduce identifier fields not present in the
initial registry. Keeping Participant as the sole identifier owner and
requiring participant-ID relationships reduces duplication. Documentation must
remain clear that identifier separation is not anonymization.

Private storage throughput
--------------------------

Proxying private S3 media through PsyNet is simple but may move bandwidth and
range-request load onto the application server. Storage interfaces should keep
the serving mechanism replaceable so that expiring URLs or a CDN can be added
without changing object identity.

Cache growth
------------

An immutable global cache grows monotonically without garbage collection.
Inspection and manual pruning are required before automatic policy is
considered.

Dashboard limits
----------------

Even after CPU and filesystem improvements, a dashboard archive must read and
transmit every selected asset. Large repeat exports should use the command-line
cache rather than the dashboard.
