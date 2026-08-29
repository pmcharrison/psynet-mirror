Documented that modules sitting beside ``experiment.py`` (for example
``adaptive_logic.py``) are imported with ``from . import my_module``. Dallinger
imports the experiment directory as a package, so a plain
``import my_module`` fails in the web, worker, and clock processes.
