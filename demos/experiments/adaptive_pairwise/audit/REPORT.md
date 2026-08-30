# Experiment audit report

## What was implemented

`demos/experiments/adaptive_pairwise` is a 100-item two-alternative forced-choice
preference experiment used to dogfood the adaptive-experiment skill, especially
the slow-to-fit posterior path.

Participants complete one practice choice and 20 scored comparisons. The item
bank is `stimuli/item_bank.csv`. The adaptive unit is a pair from a balanced
500-pair graph (every item has ten neighbors), not the full 4,950-pair matrix.
That graph was chosen after a 4,950-node `StaticTrialMaker` discovery path made
assignment too slow under concurrency.

The learner is a Bradley--Terry model with a Gaussian prior, Laplace
uncertainty, and 2,048 bootstrap refits. Fitting is intentionally slow
(about 3.3 seconds for 1,000 observations in a dedicated benchmark). A scheduled
task claims a unique data version, fits in a `WorkerAsyncProcess`, and
publishes an append-only `ready` snapshot. Selection reads only the newest
ready snapshot. Refits wait for 40 new finalized observations so refresh demand
cannot grow faster than a loaded study.

Raw answers (`Left item` / `Right item`) are kept beside the Boolean
observation `chosen_left`. Each assignment stores reconstructible candidate
provenance, objective components, snapshot and data versions, an observation
fingerprint, optimizer version, scoring time, and the binary posterior
predictive used at assignment.

Scientific response generation lives in `response_model/`. Fitting and pair
scoring live in PsyNet-independent `adaptive_logic.py`.
`simulate_procedure.py` runs the same policy against a random baseline.

This request skipped human plan review because it is workflow dogfooding.
Scientific sample size and item content remain provisional.

## Commands and evidence

- Isolated logic tests: `pytest -q tests/isolated/experiments/test_adaptive_pairwise_logic.py` (5 passed).
- Experiment import: `python experiment.py` reports 100 items and 500 pairs.
- Dedicated fit benchmark: 2,048 bootstrap refits on 1,000 observations took 3.34 seconds; pair scoring stayed in milliseconds.
- Concurrent functional bots: `psynet test local --parallel --time-factor 0` with four bots passed (mean HTTP 0.596 seconds; mean completion 89 seconds).
- Simulated export: `psynet audit simulate` wrote `audit/simulate/analysis/simulated_export/`. After a worker-only `seed` bug was fixed, 15 non-prior snapshots published as `ready` and later trials referenced fitted snapshots.
- Analysis: executed `audit/simulate/analysis/analysis.ipynb`.
- Design simulation: `python -m audit.simulate.design.core` plus executed `audit/simulate/design/simulation.ipynb`.
- Sustained load: `psynet audit performance-test --n-bots 40 --duration-minutes 5 --time-factor 1.0` wrote `audit/artifacts/performance.json` twice. Both runs completed 0 of 40 bots.

Participant video, screenshots, and a monitor snapshot were skipped after an
explicit request not to test the server UI.

## Analysis findings

The four-bot export is a misspecified synthetic-response path, not human data.
It confirms the adaptive data contract: one decision per trial, raw and
transformed answers, reconstructible candidate sets, and successful
asynchronous snapshots. Several fits exceeded two seconds while selection
scoring stayed well below one second.

The matched-budget design simulation did not meet the prespecified criterion.
At 300 observations, adaptive-minus-random RMSE was about +0.047 in the
matching scenario and +0.085 under misspecification. That negative result was
kept without post-hoc policy tuning. Infrastructure dogfooding succeeded; this
policy should not be recommended for a scientific study without a revised
objective.

## Remaining blockers

- Canonical 40-bot / 5-minute performance evidence: 0 completions, median
  response about 1.13 seconds, p95 about 23 seconds. Four-bot concurrent flow
  is acceptable; 40-way `StaticTrialMaker` candidate materialization is not.
  Next step is a PsyNet-level candidate-query optimization or a different
  assignment architecture, not a silent change to the agreed model.
- Participant video, screenshots, and monitor snapshot: skipped by request.

Automatic `/branch-review` has not been run.
