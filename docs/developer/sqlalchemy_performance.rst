.. _sqlalchemy_performance_decisions:

=========================================
SQLAlchemy performance investigation notes
=========================================

This page records lessons from profiling PsyNet's participant-navigation and
trial-assignment paths. It is a decision record rather than a list of permanent
prohibitions: rejected approaches can be reconsidered when new measurements or
APIs change their trade-offs.

The investigation deliberately excluded data export, whose implementation was
under active development.

Profiling method
================

Start with the :ref:`SQLAlchemy profiler <sqlalchemy_profiling>` and enable
stack capture:

.. code-block:: console

   psynet test local --sql-profile \
     --sql-profile-options "min_ms=0,top_n=100,stack=1"

Keep these distinctions in mind when interpreting a report:

* **Statement count** finds lazy-loading N+1 patterns, but a constant number of
  statements can still become slower as the candidate pool grows.
* **SQL execution time** does not include all Python-side ORM construction and
  deserialization. Compare request wall time as well.
* **Row count** matters even when query count does not. Loading 2,000 rows and
  discarding 1,800 in Python is still expensive.
* **Commit time** is reported separately. Moving or removing a commit can alter
  durability and transaction semantics, so it is not merely a query
  optimization.

For navigation investigations, separate ``/timeline`` and ``/response`` stacks
from setup, schema inspection, test-only status endpoints, teardown, and
export. Compare equivalent participant flows and candidate-pool sizes. Treat
single-run timings cautiously because PostgreSQL caches and machine load can
easily move small measurements.

For durable performance gates, use same-runner comparisons as described in
:ref:`asv_performance_tests`.

Patterns worth keeping
======================

Load relationships for the request that needs them
--------------------------------------------------

``Participant`` relationships such as module states and active barriers use
select-in loading because that is efficient when loading many participants.
Participant-facing routes normally load exactly one participant, and many
pages do not use all these relationships.

A request-specific query can override those relationships to ordinary lazy
loading. This avoids unconditional statements while preserving normal
relationship access later in the request. Keep this override private to the
request path: public participant getters may be used after their session is
detached and should retain their established eager-loading behavior.

Filter before ORM hydration
---------------------------

Apply known identifiers in SQL rather than loading a broad result and filtering
it in Python. For example, a performance check for one trial maker should
filter by both ``participant_id`` and ``trial_maker_id``.

This is especially important for checks that run after every trial. Repeatedly
loading an ever-growing participant history can otherwise produce quadratic
total ORM work over the experiment.

Use foreign keys when only the identifier is needed
---------------------------------------------------

Code that only logs or compares a related object's identifier should generally
read the foreign-key column, for example ``node.network_id``, rather than
accessing ``node.network.id`` and potentially resolving a relationship.

Approaches considered but not retained
======================================

Deferring mapped network counts during discovery
------------------------------------------------

Trial networks expose mapped aggregate properties such as
``n_completed_trials``. Omitting their correlated subqueries made the discovery
statement cheaper, but it changed later property access into a lazy query.
An author hook that sorted every candidate by such a property could therefore
issue one query per candidate.

The measured wall-time improvement did not justify introducing that public
footgun. Keep the current loading behavior unless a future design provides
bulk aggregate values to selection hooks.

Injecting the loaded network into ``Node.network``
--------------------------------------------------

Loading ``ChainNetwork.head`` does not populate ``head.network`` automatically:
the former uses ``network.head_id -> node.id``, while the latter uses
``node.network_id -> network.id``. They are not ``back_populates`` counterparts.

SQLAlchemy's ``set_committed_value`` can inject the already-loaded network
without marking the node dirty. This can save a relationship lookup, but it
also bypasses normal relationship history and requires careful handling of
dirty or inconsistent objects. The small measured benefit did not justify this
specialized state manipulation.

Using the growth poller as a request-path predicate
---------------------------------------------------

The scheduled growth poller is designed to find and lock batches of ready
networks. Reusing it for every finalized trial looked attractive because its
SQL predicate avoids hydrating all trials at a node.

In practice this approach had several drawbacks:

* static networks paid a readiness query even though they cannot grow;
* common chain cases traded a small relationship load for a lock query and a
  wide polymorphic network refresh;
* the lock and ``skip_locked`` behavior changed the semantics of a method that
  previously behaved like a predicate;
* calling a private helper directly bypassed subclasses overriding the public
  readiness method;
* graph growth could capture a head before the refresh and then grow stale
  state.

Keep request-path readiness and scheduled batch growth separate unless a future
API explicitly returns a locked, refreshed network and preserves the public
extension point. Benchmark static, ordinary chain, and graph cases—not only
nodes with very large trial histories.

Undeferring experiment variables through ``Query.get``
------------------------------------------------------

``ExperimentConfig.vars`` is deferred because JSON variable stores can be
large. Adding ``undefer`` to ``Query.get`` does not reliably combine row and
variable loading when SQLAlchemy satisfies ``get`` from the identity map;
loader options may not run on that path.

If this is revisited, choose an approach with explicit identity-map semantics,
such as changing the singleton's mapping or issuing an explicit refresh.
Test fresh, expired, and already-present identity-map states.

A generic N+1 assertion helper
------------------------------

A helper that flags any statement repeated at least once per candidate is only
a heuristic. It can split identical SQL by captured stack, flag legitimate
constant repetition for small pools, or become redundant when the enclosing
test already has a lower total-query budget.

Prefer focused tests that compare query counts for small and large candidate
pools, alongside explicit maximum query budgets around author hooks. Such tests
state the scaling contract directly.

Small SQL-shape special cases
-----------------------------

Special-casing an empty ``IN``/``NOT IN`` input can make generated SQL look
cleaner, but SQLAlchemy already emits a correct no-op predicate. Do not add a
branch unless profiling demonstrates a meaningful benefit.

Remaining opportunities
=======================

Item-level selection
--------------------

Static trial makers still hydrate candidate network and node objects. Statement
count can remain constant while Python work grows linearly with a large item
bank. A future item-level API could select a lightweight item row in SQL and
materialize only the chosen trial. Such an API needs explicit decisions about
capacity, participant exclusions, concurrency, assets, provenance, and
transactional reservation.

Request telemetry
-----------------

Request telemetry inserts and commits a row after participant-facing requests.
Local profiling observed a small per-request cost, but changing this path
affects metric durability and transaction boundaries. Revisit it only with a
clear durability policy and concurrent-load evidence.

Route-level regression coverage
-------------------------------

Focused ORM tests are fast and useful, but they do not guarantee that
``/timeline`` and ``/response`` continue using the intended query construction.
A small HTTP-level query-budget test would provide stronger coverage if it can
isolate the server process's profiler without becoming timing-sensitive.

Evidence from the investigation
===============================

The following figures are local observations, not portable performance
guarantees:

* In one matched timeline flow, request-scoped participant loading reduced the
  participant-load statements from about four per request to one. Mean
  participant-facing HTTP duration moved from 72 ms to 69 ms.
* In a synthetic multi-module performance-check benchmark, filtering by trial
  maker in SQL hydrated 200 rows instead of 2,000 and reduced the measured
  lookup from 44.1 ms to 5.7 ms.

These results justify the retained changes, but production impact depends on
database size, concurrency, experiment structure, and authored callbacks.

Checklist for future investigations
===================================

#. Reproduce the participant flow before changing code.
#. Capture stacks and retain raw profiler output.
#. Compare statement count, SQL time, rows hydrated, request time, and commits.
#. Sweep the dimension expected to scale, such as candidates or completed
   trials.
#. Test public hooks and detached ORM objects, not only built-in paths.
#. Include static, chain, graph, and synchronized paradigms when changing shared
   trial-maker infrastructure.
#. Prefer a focused SQL filter or loader option over custom ORM state
   manipulation.
#. Record why an attractive approach was rejected and what evidence would
   justify revisiting it.
