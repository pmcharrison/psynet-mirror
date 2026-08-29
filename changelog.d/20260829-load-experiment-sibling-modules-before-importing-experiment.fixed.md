Fixed loading of sibling experiment modules (for example ``adaptive_logic.py``)
when PsyNet imports ``experiment.py``. The experiment directory is now placed on
``sys.path`` before Dallinger loads the experiment class.
