Added ``psynet audit simulate``, which runs experiment bots, writes their export
directly to ``./audit/artifacts/simulated_data.zip``, and marks
``simulation_export`` present. Use ``--no-mark-present`` to write the zip
without updating ``audit.json``.
