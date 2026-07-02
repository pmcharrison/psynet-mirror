.. _asv_performance_tests:
.. highlight:: shell

=====================
ASV performance tests
=====================

PsyNet uses `Airspeed Velocity (ASV) <https://asv.readthedocs.io/>`_ to track
performance over time. The benchmark configuration lives in ``asv.conf.json``,
benchmark code lives in ``benchmarks/``, and CI stores generated result files on
the ``benchmark-results`` branch.

Benchmark tiers
===============

Benchmarks are split by directory:

- ``benchmarks/fast/`` contains quick hot-path benchmarks. Merge requests run
  these as the ASV regression gate.
- ``benchmarks/slow/`` contains end-to-end experiment performance benchmarks.
  These are intentionally excluded from the merge-request gate, but they do run
  on ``master``.

Merge-request checks
====================

Merge requests run the ``asv_regression`` CI job. This job uses
``asv continuous`` with ``--bench "^fast\\."`` to benchmark the merge-request
base and head commits back-to-back on the same GitLab runner. The job exits
non-zero when ASV detects a regression larger than the configured factor.

Default-branch checks and publishing
====================================

Commits to ``master`` run the ``asv_benchmarks`` CI job. This job uses
``asv continuous`` without a ``--bench`` filter, so it runs both the fast and
slow benchmark tiers. It compares the previous ``master`` commit with the new
commit on the same runner, writes the generated result files, commits those
results to the ``benchmark-results`` branch, pushes them, and then propagates
the ASV exit status. This means ``master`` CI fails on performance regressions
while still preserving the data needed for the published benchmark history.

ASV command modes
=================

The helper script ``ci/asv-sync-results.sh`` supports two ASV command modes:

- ``asv run`` benchmarks selected commits and records their results. Use this
  when you only need fresh benchmark data.
- ``asv continuous BASE HEAD`` benchmarks ``BASE`` and ``HEAD`` back-to-back on
  the same runner, compares the results, and exits non-zero if ``HEAD``
  regresses. Use this when benchmark results should also act as a regression
  gate.

Local commands
==============

Run the fast tier locally:

.. code-block:: shell

    asv run --quick --show-stderr --bench '^fast\.'

Run a same-runner comparison locally:

.. code-block:: shell

    asv continuous --factor 1.25 --split --show-stderr --bench '^fast\.' BASE HEAD

Preview published benchmark results locally:

.. code-block:: shell

    bash ci/asv-local.sh

The preview command fetches the ``benchmark-results`` branch, runs
``asv publish``, and serves the generated pages at ``http://127.0.0.1:8080``.
