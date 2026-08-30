Moved audit evidence collection to ``psynet audit simulate`` and
``psynet audit performance-test local``. These commands require an initialized
audit packet, write canonical evidence paths, and update ``audit.json``.
Top-level ``psynet performance-test`` remains available for measurement-only
runs and no longer accepts ``--audit``. Simulated exports now exist only at
``audit/simulate/analysis/simulated_export/``.
