.. _asv_performance_tests:
.. highlight:: shell

=====================
ASV performance tests
=====================

PsyNet uses `Airspeed Velocity (ASV) <https://asv.readthedocs.io/>`_ to track
performance over time. The benchmark configuration lives in ``asv.conf.json``,
benchmark code lives in ``benchmarks/``, and CI stores generated result files on
the ``benchmark-results`` branch.

.. note::

    This page describes how PsyNet benchmarks *its own* performance across
    commits. If instead you want to load-test *your experiment* to check how it
    will cope with real participants, see the
    :ref:`testing experiment performance tutorial <performance_testing>`. The
    slow ASV tier below drives that same ``psynet performance-test`` command
    under the hood.

Benchmark tiers
===============

Benchmarks are split by directory:

- ``benchmarks/fast/`` contains benchmarks selected for the merge-request
  regression gate, including quick hot paths and focused end-to-end checks.
- ``benchmarks/slow/`` contains end-to-end experiment performance benchmarks.
  These are intentionally excluded from the merge-request gate, but they do run
  on ``master``. The slow ASV history focuses on median request latency and
  median async-process queue delay; participant failures and incomplete bots are
  left in the performance-test output instead of being tracked as ASV metrics.

Merge-request checks
====================

Merge requests run the ``asv_regression`` CI job. This job uses
``asv continuous`` with ``--bench "^fast\\."`` to benchmark the merge-request
base and head commits back-to-back on the same GitLab runner. The job exits
non-zero when ASV detects a regression larger than the configured factor.

Export benchmarks in ``benchmarks/fast/export_benchmarks.py`` skip on a
merge-base whose installed PsyNet predates ``psynet.export``. Their
``setup_cache`` returns ``None`` in that case, and ASV then calls
``setup(profile)`` with no cached results dict, so ``setup`` accepts an
optional ``profile`` and raises ``NotImplementedError`` to mark the skip.
Those benchmarks have no baseline to compare against until they exist on
both sides of the comparison.

``track_*`` methods record one scalar and have no ASV warmup. ``asv continuous``
interleaves rounds by default, so a later round can run HEAD before BASE.
``--split`` only splits the results table. A cold first asset export
fills ``~/psynet-data/cache/assets`` for the other commit, so that second
commit looks faster even when the merge request did not touch export.

``LocalAssetExport`` sets ``PSYNET_ASSET_CACHE_ROOT`` to an isolated
directory, discards one ``psynet export local --assets collected`` run, and
records a second CLI export.
Incremental remote asset transfer is covered by functional tests rather than
ASV metrics, because the warm-cache path is dominated by filesystem noise and
has produced unstable ratios under the merge-request gate's ``--factor 1.25``.

Default-branch checks and publishing
====================================

Commits to ``master`` run the ``asv_benchmarks`` CI job. This job uses
``asv continuous`` without a ``--bench`` filter, so it runs both the fast and
slow benchmark tiers. It compares the previous ``master`` commit with the new
commit on the same runner, writes the generated result files, commits those
results to the ``benchmark-results`` branch, pushes them, and then propagates
the ASV exit status. The job is currently allowed to fail while the benchmark
suite is being tuned, but it still preserves the data needed for the published
benchmark history.

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
