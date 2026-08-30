# Plan

## Methods

### Design

Participants complete 20 two-alternative forced-choice comparisons drawn from a
fixed bank of 100 abstract visual items. A balanced sparse graph supplies 500
candidate pairs, giving every item ten neighbors without imposing the request
cost of materializing all 4,950 possible pairs. Each candidate pair is eligible
at most once per participant. The adaptive unit is the item pair. Left/right
position is randomized after selection and the raw answer is retained.

The 20-trial budget is provisional workflow-test scaffolding, not a
scientifically powered sample size. The design simulation compares adaptive and
random selection at matched observation budgets before this value is used in a
real study.

### Materials

`stimuli/item_bank.csv` is the deployment-safe manifest. It gives every item a
stable ID, display label, color hue, and simulation-only latent rank. The latent
rank generates synthetic responses and is not treated as known participant
behavior.

### Procedure

Participants read brief instructions, complete one unscored practice choice,
and then choose the preferred item in 20 pairs. There are no correct answers.

## Adaptive specification

These choices are explicit assumptions made to dogfood the workflow without
waiting for human review:

- Observation \(y\): `chosen_left`, a Boolean transformed from the retained raw
  answers `Left item` and `Right item`.
- Covariates \(z\): an empty vector. This first model has no participant or
  contextual covariates.
- Adaptive unit: one unordered pair from the balanced 500-pair candidate graph.
- Learner: a Bayesian Bradley--Terry model with item utilities, a Gaussian
  prior, and the final item fixed as the reference.
- Simulation response model: a matching Bradley--Terry model and a
  misspecified model with lower choice consistency, lapses, and left bias.
- Posterior strategy: `from_scratch`; a MAP/Laplace approximation plus 2,048
  nonparametric bootstrap refits.
- Optimization: maximize posterior predictive entropy weighted by pairwise
  uncertainty, with seeded tie-breaking.
- Persistence: append-only SQL snapshots. Selection reads only the newest
  `ready` snapshot; fitting happens in a scheduled task and publishes
  atomically.
- Dependencies: NumPy and SciPy only; no probabilistic-programming runtime.

Every assignment stores a digest and count of the candidate IDs, the short list
of excluded IDs needed to reconstruct the exact set from the versioned manifest,
the chosen pair, objective components, snapshot and data versions, observation
fingerprint, optimizer version, selection timing, and the free binary posterior
predictive distribution.

## Implementation

Use a `StaticTrialMaker` because candidate pairs are fixed and independent.
Override `select_node` for ranking and `on_trial_created` for transactional
decision provenance. Keep scientific response generation in `response_model/`
and PsyNet-independent inference and policy code in `adaptive_logic.py`.

The model fit is intentionally expensive: 2,048 bootstrap refits take several
seconds once data accumulate. A scheduled task claims a unique data version,
fits outside the database transaction, and atomically marks the snapshot
`ready`. The participant request path only scores the compact state and must
remain below one second.

## Workflow review assumption

The original request is specifically to dogfood the implementation workflow.
The normal human plan-approval pause is therefore skipped. Scientific sample
size and item content remain explicitly provisional.
