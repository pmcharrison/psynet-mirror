# Implementation notes

This packet is a dogfood of the PsyNet experiment-implementation workflow.
The experiment is a 32-item 1PL arithmetic CAT using `Trial.cue`.

## What was built

- `stimuli/item_bank.json`: judgement-calibrated four-choice arithmetic items.
- `response_model/core.py`: 1PL / 3PL sampling used by bots and simulations.
- `adaptive_logic.py`: from-scratch grid posterior, max Fisher information,
  min/max/SE stopping. No PsyNet imports.
- `simulate_procedure.py`: standalone CAT vs random selection.
- `experiment.py`: practice module, CAT `while_loop`, `AdaptiveDecision`
  rows created in `on_trial_created`, `get_basic_data` exports.

Human plan review was skipped (dogfood). Labeled assumptions are in `PLAN.md`.

## Validation

- Isolated CAT tests: 7 passed (`tests/isolated/test_adaptive_irt_logic.py`).
- `psynet test local`: 3 bots completed 16 scored items each; 48 decision rows.
- `python audit/simulate/design/core.py`: 20 replicates, 144 result rows.
- `psynet estimate --mode both`: $0.48, 2 min 25 s at $12/hour.
- `psynet audit simulate`: export under `simulate/analysis/simulated_export/`.
- `psynet performance-test local --n-bots 6 --duration-minutes 1`: median
  HTTP 0.13 s, p95 1.3 s, 0/6 bots finished because the CAT is longer than
  one minute. This is a smoke run, not a 40-bot 5-minute load test.

Scaffolded `config.txt` already sets `wage_per_hour`; putting the same key in
`Experiment.config` raises. Keep wage in `config.txt` only.

`participant.var.get("fit")` raises `KeyError` unless a default is passed.

Bundled demos gitignore `__init__.py`, so `python -m audit.simulate.design.core`
is not a reliable invocation here. The runner is
`python audit/simulate/design/core.py` and adds the experiment root to
`sys.path`.

## Design simulation

Max-information CAT is a bit more precise than random order (RMSE 0.48 vs
0.53 at 16 well-specified items) but does not meet the pre-set RMSE 0.45
target. The SE 0.40 stopping rule never shortened tests. 3PL guessing
inflates RMSE for both policies. The demo still ships the adaptive policy
because the brief is to exercise the workflow, not to claim a powered study.

## Limitations

Bot data are not human data. Item difficulties are not empirically
calibrated. The three bot profiles (`good` at θ=-1.2 and 0.3, `inattentive`
at stored θ=1.4 with guessing/lapse) only check export plumbing.
