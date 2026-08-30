``import_local_experiment()`` no longer appends the experiment directory to
``sys.path``. This does not change how ``experiment.py`` must import siblings:
``from . import adaptive_logic`` was already required when Dallinger loads the
experiment as a package. The only code that used to work and now fails is a
later bare import after the experiment class is loaded, for example
``import adaptive_logic`` inside a function. Import the sibling relatively at
module level and call that name instead. See the experiment-directory docs
section "Importing other Python files".
