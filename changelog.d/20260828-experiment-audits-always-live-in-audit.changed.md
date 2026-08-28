Experiment audits always live in ``./audit/`` under the experiment
directory. ``psynet audit`` commands take no packet path; pass
``--experiment`` only when the current directory is not the experiment (or
``audit/``). Passing an existing ``audit/`` packet as ``--experiment`` is an
error. ``--audit`` on simulate and performance-test is a boolean flag that
writes into that nested folder. Experiment source is the parent of
``audit/``; leftover ``experiment.source_path`` and
``experiment.source_base`` fields are ignored with a warning.
