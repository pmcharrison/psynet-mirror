Adaptive arithmetic IRT
=======================

Source: ``demos/experiments/adaptive_irt``

This demo is a small computerized adaptive test. Participants answer
four-choice mental-arithmetic questions. After each scored response, a 1PL
Rasch model updates a grid posterior over ability, and the next unused item is
the one with the highest expected Fisher information.

The adaptive policy lives in ``adaptive_logic.py``, which does not import
PsyNet. ``experiment.py`` loads observations, cues the selected item with
:meth:`~psynet.trial.main.Trial.cue`, and writes an ``AdaptiveDecision`` row in
the same transaction via ``on_trial_created``. ``simulate_procedure.py`` runs
the same loop outside PsyNet so power analysis can compare max-information
selection with random item order.

.. literalinclude:: ../../demos/experiments/adaptive_irt/experiment.py
   :language: python
   :lines: 1-80
