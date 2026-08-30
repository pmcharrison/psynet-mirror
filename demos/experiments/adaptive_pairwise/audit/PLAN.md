# Plan

## Methods

### Design

Participants complete 20 two-alternative forced-choice comparisons drawn from a
fixed bank of 100 synthesized audio items. A balanced sparse graph supplies 500
virtual candidate pairs, giving every item ten neighbors without materializing
pair nodes in the database. Each candidate pair is eligible at most once per
participant. The adaptive unit is the item pair. First/second presentation is
randomized after selection and the raw answer is retained.

The 20-trial budget is provisional workflow-test scaffolding, not a
scientifically powered sample size. The design simulation compares adaptive and
random selection at matched observation budgets before this value is used in a
real study.

### Materials

`stimuli/item_bank.csv` is the deployment-safe manifest. It gives every item a
stable ID and simulation-only latent rank. The worked example generates one
short cached tone per item, so asset growth is linear in items rather than
quadratic in pairs. The latent rank determines demonstration frequency and
synthetic responses; it is not treated as known participant behavior.

### Procedure

Participants calibrate their volume, read brief instructions, acknowledge one
unscored practice page, and then choose the preferred sound in 20 sequentially
presented pairs. There are no correct answers.

## Adaptive specification

These choices are explicit assumptions made to dogfood the workflow without
waiting for human review:

- Observation \(y\): `chosen_left`, a Boolean transformed from the retained raw
  answers `First sound` and `Second sound`.
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
- Dependencies: NumPy, SciPy, and SoundFile; no probabilistic-programming runtime.

Every assignment stores a digest and count of the candidate IDs, the short list
of excluded IDs needed to reconstruct the exact set from the versioned manifest,
the chosen pair, objective components, snapshot and data versions, observation
fingerprint, optimizer version, selection timing, and the free binary posterior
predictive distribution.

## Implementation

Use a runtime `for_loop` and `Trial.cue` because pair candidates are virtual.
The pair policy reads the item manifest and latest snapshot, then cues only the
selected definition with references to its two module-level audio assets.
`Trial.cue(on_trial_created=...)` persists decision provenance in the same
transaction as the trial. Keep scientific response generation in
`response_model/` and PsyNet-independent inference and policy code in
`adaptive_logic.py`.

The model fit is intentionally expensive: 2,048 bootstrap refits take several
seconds once data accumulate. A scheduled task claims a unique data version,
fits outside the database transaction, and atomically marks the snapshot
`ready`. Refreshes are batched after at least 40 new finalized observations so
fit demand cannot grow faster than a heavily loaded study. The participant
request path only scores the compact state and must remain below one second.

## Workflow review assumption

The original request is specifically to dogfood the implementation workflow.
The normal human plan-approval pause is therefore skipped. Scientific sample
size and item content remain explicitly provisional.
