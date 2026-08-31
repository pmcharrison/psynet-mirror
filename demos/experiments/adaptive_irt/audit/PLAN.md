# Plan

Human plan review was skipped: this experiment is a dogfood of the agent
implementation workflow, not a commissioned study.

## Science

The demo estimates each participant's latent arithmetic ability on a 1PL
(Rasch) scale. It is a worked example of computerized adaptive testing, not a
substantive research project. There is no population-level scientific
hypothesis beyond "max-information item selection recovers ability more
precisely than random item order at a matched test length."

## Methods

Design. Each participant completes two practice items with feedback, then a
scored CAT. The adaptive unit is a single multiple-choice arithmetic item.
Scored length is at least 8 and at most 16 items. The test may stop early
when the posterior standard deviation of ability is at most 0.40. There are
no between-participant conditions in the live experiment; policy comparisons
live in the offline design simulation.

Materials. A committed bank of 32 four-choice mental-arithmetic items in
`stimuli/item_bank.json`, each with a pre-calibrated difficulty. Difficulties
are judgement-based, not empirically calibrated. Practice uses two easy items
from the same bank.

Procedure. Instructions, practice with feedback, adaptive scored items without
trial-by-trial feedback, then a short summary of the estimated skill. Bots
store a `true_ability` and `response_profile` (`good` vs `inattentive`) on
participant vars so exports can distinguish simulation profiles.

## Adaptive specification

These choices are workflow assumptions for the dogfood, labelled as such.

- Observation `y`: `correct`, a 0/1 score from whether the chosen option
  equals `correct_choice`. The raw button label remains in `trial.answer`.
- Covariates `z`: none. The learner is an intercept-only 1PL.
- Adaptive unit: `item_id` from the committed item bank.
- Learner model: 1PL with known item difficulties,
  `P(correct) = logistic(theta - b)`, `theta ~ Normal(0, 1)`.
- Simulation response model: the same 1PL for well-specified bots; a 3PL with
  guessing 0.25 (and inattentive bots also lapse) for misspecification.
- Posterior strategy: `from_scratch` discrete grid (161 points on [-4, 4]).
- Optimization policy: maximum expected Fisher information; ties broken by
  `item_id`. Early stopping as above.
- Persistence: participant posterior is recomputed from finalized adaptive
  trials. Selection provenance is stored in `adaptive_decision` rows.
- Dependencies: NumPy only for the learner (no probabilistic programming
  library), matching the conjugate/simple-grid guidance.

## Power analysis

Provisional design (to be confirmed by `audit/simulate/design`): 12 expected
scored items, stopping at SE 0.40 after 8 items, maximum 16. The primary
decision metric is RMSE of the posterior mean versus true ability, with
threshold 0.45 under the well-specified 1PL. Candidate designs vary test
length (8, 12, 16) and policy (max information vs random without replacement).
A 3PL-guessing scenario checks robustness. Participant payment uses the
timeline time estimates at $12/hour.

## Implementation

- `response_model/` samples synthetic answers.
- `adaptive_logic.py` fits the grid posterior and selects items.
- `simulate_procedure.py` runs the CAT loop without PsyNet.
- `experiment.py` uses `Trial.cue` inside a `while_loop`, `Module`s for
  practice and CAT, `AdaptiveDecision` via `on_trial_created`, and
  `get_basic_data` for trial, participant, and decision exports.
- Practice and CAT are ordinary PsyNet pages (`ModularPage` +
  `PushButtonControl`); no custom JavaScript.
