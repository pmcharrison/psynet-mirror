Documented how to import Python files that sit beside ``experiment.py``.
From the experiment package use ``from . import my_module`` and call that
name later, for example ``adaptive_logic.select_item(...)``. Standalone
scripts such as ``python -m audit.power.core`` keep top-level imports.
The experiment-directory docs, troubleshooting page, and back-end skill
describe these patterns.
