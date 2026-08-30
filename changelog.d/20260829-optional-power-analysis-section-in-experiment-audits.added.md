Added an optional power-analysis section to experiment audits. A power analysis
now lives at ``audit/power/`` instead of the experiment root, and
``psynet audit render`` shows its executed notebook, run provenance, and
supporting files. Packets that omit the section but still have ``power/`` files
get a Power analysis panel; packets that hide the section with
``"display": false`` keep it hidden. ``psynet audit init`` creates the directory
and declares the optional ``power_analysis``, ``power_run``, and
``power_results`` artifacts, which stay ``missing`` without a blocker when an
experiment needs no power analysis.
