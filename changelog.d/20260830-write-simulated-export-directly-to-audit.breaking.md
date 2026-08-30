``psynet simulate`` now requires an initialized audit packet and writes its
only export to ``audit/simulate/analysis/simulated_export/``. The command no
longer accepts ``--audit`` or writes ``data/simulated_data/``; use
``--no-mark-present`` to skip updating ``audit.json``.
