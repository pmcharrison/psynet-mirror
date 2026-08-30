Documented how to import Python files that sit beside ``experiment.py``.
From the experiment package use ``from . import my_module``. Standalone
scripts such as ``python -m audit.power.core`` keep top-level imports.
The experiment-directory docs are the full reference; skills show the
import line and point there.
