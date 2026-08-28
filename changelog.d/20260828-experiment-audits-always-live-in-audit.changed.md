Experiment audits always live in ``./audit/`` under the experiment
directory. ``psynet audit init`` and ``init .`` create that nested folder;
``experiment.source_path`` is relative to the experiment root (the parent of
``audit/``). Leftover flat ``audit.json`` packets are rejected, and a leftover
``experiment.source_base`` field is ignored with a warning.
