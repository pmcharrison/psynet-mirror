---
name: make-experiment-adaptive
description: Implement a PsyNet experiment in which accumulated responses influence later measurements or assignments.
---

# Make an experiment adaptive

An adaptive experiment uses earlier responses to decide what to measure next.
Classify the procedure by the level at which its adaptive state is maintained:

| Level | Information used for selection | Examples |
| --- | --- | --- |
| Participant-level adaptation | The current participant's response history and a fixed item or task model | Computerized adaptive testing; psychophysical staircases |
| Study-level adaptation | Accumulated responses shared across participants | Active learning; adaptive experimental design |
| Combined adaptation | Participant-level and study-level state | Online-calibrated adaptive testing |

State separately what the procedure estimates: participant attributes, item
attributes, population parameters, or a combination. The two levels may use
different models and update schedules; do not force them through one generic
state object.

## Layout

Keep the adaptive models and selection policy outside `experiment.py`:

```text
experiment.py
adaptive_logic.py
simulate_procedure.py
response_model/
├── __init__.py
└── core.py
power/
├── config.toml
├── core.py
├── results.csv
├── run.json
└── analysis.ipynb
benchmark/
└── same files as power/
```

`adaptive_logic.py` contains the fitting and selection functions used by both
PsyNet and the standalone simulation. It must not import PsyNet or SQLAlchemy.

`simulate_procedure.py` runs one complete adaptive experiment without starting
PsyNet. It maintains the observation, participant, item, and decision tables;
calls `adaptive_logic.py` to select each assignment; and draws the resulting
response from `response_model/`. This standalone simulation tests the
scientific procedure at scale; `psynet simulate` is still needed to test its
integration with the PsyNet timeline, response handling, and export path.

`power/` follows `power-analysis/SKILL.md`; `benchmark/` follows
[references/benchmark-adaptive-procedure.md](references/benchmark-adaptive-procedure.md).
Both call `simulate_procedure.py` across designs, assumptions, and replicates.
Keep the adaptive loop there rather than recreating it in either analysis.

`response_model/` follows `participant-response-models/SKILL.md` and generates
synthetic participant responses. The adaptive model estimates quantities used
for selection, whereas the response model supplies assumed behaviour for
simulations and bots. They may share mathematical components.

## Use three related tables

Use the same three-table boundary in PsyNet, standalone simulations, and
analysis code:

```python
observations
# response | participant_id | item_id | trial_order | ...

participants
# participant_id | condition | ...

items
# item_id | category | difficulty | ...
```

`participant_id` must be unique in `participants`, `item_id` must be unique in
`items`, and observation IDs must refer to rows in those tables. Additional
columns should have domain-specific names. The examples below retain these ID
columns while also using them as the dataframe indexes.

Pass these tables directly to the adaptive functions. Each model may perform
its own joins and convert columns to NumPy arrays, sparse matrices, tensors, or
another numerical representation. Pass an explicit random-number generator
when fitting or selection is stochastic.

## Participant-level adaptation

When item parameters are already calibrated, load the immutable item table once
per server process and retain its stable item-ID mapping:

```python
ITEMS = pd.read_csv("data/item_bank.csv").set_index("item_id", drop=False)
```

Selection normally updates one participant estimate and scores the remaining
items:

```python
participant_observations = observations[
    observations["participant_id"] == participant_id
]

participant_fit = fit_participant_model(
    observations=participant_observations,
    participant=participants.loc[participant_id],
    items=ITEMS,
)

utilities = score_items(
    participant_fit=participant_fit,
    candidate_items=candidate_items,
)
```

This calculation can normally remain in the participant-facing path. Recompute
the participant estimate from their finalized responses, or treat a cached
estimate as an optimization rather than the authoritative record. Shared item
exposure constraints introduce study-level state and should use the safeguards
below.

## Study-level adaptation

When item or population parameters are learned during collection, responses
from one participant can affect later participants. Fit the shared model from
all three tables, then score the currently available items or assignments:

```python
study_fit = fit_study_model(
    observations=observations,
    participants=participants,
    items=items,
)

utilities = score_items(
    study_fit=study_fit,
    candidate_items=candidate_items,
    participant=participants.loc[participant_id],
)
```

Omit `participant` when the study-level policy is not participant-specific. A
policy that selects recruitment strata or item-participant pairs can construct
a separate candidate table with one row per possible action.

Fit inline only when profiling shows that fitting and scoring remain comfortably
within the experiment's participant-facing latency budget. Otherwise, fit in a
background process and publish immutable, versioned study-model snapshots.
Trial selection should read the latest complete snapshot rather than wait for
or read a partially written update.

Record the response-data cutoff in every snapshot. Allow only one refresh to
claim a given update, and use a single-writer queue or database locking for truly
incremental learning. A warm start is only a starting value; the new fit must
still incorporate responses added since the previous snapshot.

Choose and document the refresh rule, such as a fixed number of new responses
or a fixed interval. Using a stale but valid snapshot, waiting for a refresh, or
falling back to a prespecified allocation policy are different experimental
designs and must not be selected silently at runtime.

## Combine both levels

Keep participant-level and study-level state distinct. For example, an
online-calibrated test can estimate the current participant from their own
responses while taking item parameters from the latest shared calibration
snapshot:

```python
study_fit = latest_study_fit()
calibrated_items = apply_calibration(items, study_fit)

participant_fit = fit_participant_model(
    observations=participant_observations,
    participant=participants.loc[participant_id],
    items=calibrated_items,
)

utilities = score_items(
    study_fit=study_fit,
    participant_fit=participant_fit,
    candidate_items=candidate_items,
)
```

Record both the participant-history cutoff and the shared snapshot version used
for each decision. The two update loops may run at different frequencies and
should be reproduced separately in simulation.

## Connect the policy to PsyNet

Choose the trial-maker architecture using
`develop-experiment-back-end/SKILL.md`. `StaticTrialMaker` represents each item
internally as the head of a network. Preserve its eligibility and allocation
logic by overriding `select_node`, then immediately translate the eligible
nodes into a candidate item table. Return the chosen node, or wrap it in
`Selection` when the decision record needs request-local context:

```python
from psynet.trial.main import Selection

class AdaptiveTrialMaker(StaticTrialMaker):
    def select_node(self, nodes, participant, experiment):
        observations = load_observation_table()
        nodes_by_item_id = {node.definition["item_id"]: node for node in nodes}
        candidate_items = ITEMS.loc[list(nodes_by_item_id)]
        utilities = adaptive_logic.score_available_items(
            observations=observations,
            participants=load_participant_table(),
            items=ITEMS,
            candidate_items=candidate_items,
            participant_id=participant.id,
        )
        selected_item_id = utilities.idxmax()
        selected_node = nodes_by_item_id[selected_item_id]
        return Selection(
            value=selected_node,
            context={
                "selected_candidate_id": selected_item_id,
                "participant_history_count": int(
                    (observations["participant_id"] == participant.id).sum()
                ),
                "study_fit_id": current_study_fit_id(),
                "candidate_pool_version": ITEM_BANK_VERSION,
                "selected_utility": float(utilities.loc[selected_item_id]),
                "details": {"n_candidates": len(candidate_items)},
            },
        )
```

Here `utilities` is a Series indexed by `item_id`. A non-adaptive override can
simply `return selected_node`. `current_study_fit_id()`
returns `None` for participant-level adaptation. `Selection.context`
travels only through the current trial-construction call; it is not stored in
participant or module state. PsyNet calls `select_node` only when at least one
eligible node exists.

`StaticTrialMaker` excludes previously visited nodes before calling
`select_node` when `allow_repeated_nodes=False`, which is the default.
Set it explicitly and keep `n_repeat_trials=0` when the participant must never
see an item twice. If several nodes represent the same logical item, use
`node_is_eligible` with a stable item identifier so every copy becomes
ineligible after the first assignment.

Use `node_is_eligible` (or batched `nodes_are_eligible`) only when the policy
changes item eligibility rather than priority; ordinary repeat suppression is
already provided by `allow_repeated_nodes=False`. On `StaticTrialMaker`,
override `select_node` rather than `find_nodes`. Chain-based adaptation
instead chooses among evolving chains with `select_chain` and
`chain_is_eligible`; it may likewise return
`Selection(value=selected_chain, context=...)`. Do not override the managed
`prepare_trial` of a `NetworkTrialMaker`.

Item selection belongs in the trial maker. Adaptive recruitment or participant
selection instead needs an experiment recruitment criterion or scheduler. A
combined policy may have both adapters call the same table-based
`adaptive_logic.py`.

The standalone simulation must apply the same eligibility rule to its decision
table rather than inferring exposure only from successful observations:

```python
seen_item_ids = decisions.loc[
    decisions["participant_id"] == participant_id,
    "selected_candidate_id",
]
candidate_items = items[~items["item_id"].isin(seen_item_ids)]
```

## Implement a custom stopping rule

Put participant-level stopping logic in `adaptive_logic.py` so PsyNet and
`simulate_procedure.py` call the same function. A typical rule combines a
minimum amount of data with a required precision; the exact inputs and return
criterion should use domain-specific names.

For a `StaticTrialMaker`, adapt PsyNet's `should_finish_block` hook:

```python
class AdaptiveTrialMaker(StaticTrialMaker):
    def should_finish_block(
        self,
        participant,
        block,
        block_position,
        n_participant_trials_in_block,
        n_participant_trials_in_trial_maker,
    ):
        if super().should_finish_block(
            participant,
            block,
            block_position,
            n_participant_trials_in_block,
            n_participant_trials_in_trial_maker,
        ):
            return True

        participant_fit = adaptive_logic.fit_participant_model(
            observations=load_participant_observations(participant),
            participant=participant_to_row(participant),
            items=ITEMS,
        )
        return adaptive_logic.should_stop_participant(
            participant_fit=participant_fit,
            n_administered=n_participant_trials_in_trial_maker,
        )
```

Calling `super()` preserves PsyNet's configured maximums. Set
`max_trials_per_participant` as a hard cap even when the scientific rule would
normally stop earlier. `expected_trials_per_participant` only controls timing
and progress estimates; it is not a stopping rule.

With one adaptive block, returning `True` ends the trial maker. With several
blocks, it ends the current block and advances to the next one, so define the
criterion accordingly. Exhausting all eligible items also ends the trial maker.
Avoid fitting the participant model twice for stopping and selection when that
cost is material; share a fit keyed by the finalized observation set.

## Store observations and decisions

An observation and a decision answer different questions. The observation says
what happened on a trial. The decision says why that trial was assigned. Store
both:

```text
decision -> assigned trial -> raw answer -> model-ready observation
```

PsyNet already stores the browser answer in `trial.answer`. Preserve this as the
authoritative response. When it already has a scientifically meaningful form,
put it directly into the observation table. A seven-point rating does not need
to be called a score.

For a small dataset, the observation table can unpack `trial.answer` and
`trial.definition` in Python. Adaptive fitting may read a large trial table
repeatedly, however. In that case, store the fields used by the model in
explicit columns while retaining the original answer:

```python
from sqlalchemy import Column, Integer, String

from psynet.trial.static import StaticTrial, StaticTrialMaker


class RatingTrial(StaticTrial):
    item_id = Column(String, index=True)
    rating = Column(Integer, nullable=True)

    def finalize_definition(self, definition, experiment, participant):
        definition = super().finalize_definition(definition, experiment, participant)
        self.item_id = definition["item_id"]
        return definition


class RatingTrialMaker(StaticTrialMaker):
    def finalize_trial(self, answer, trial, experiment, participant):
        trial.rating = int(answer)
        super().finalize_trial(answer, trial, experiment, participant)
```

Only finalized trials belong in the PsyNet observation table. This ensures that
any required asynchronous processing has succeeded. Select the required
columns directly rather than constructing full trial objects. PsyNet stores
the zero-based `Trial.position`, so it can be selected without another query.

```python
from dallinger import db
from sqlalchemy import select


statement = (
    select(
        RatingTrial.id.label("observation_id"),
        RatingTrial.participant_id,
        RatingTrial.item_id,
        RatingTrial.rating,
        RatingTrial.position.label("trial_order"),
    )
    .where(
        RatingTrial.finalized.is_(True),
        RatingTrial.failed.is_(False),
        RatingTrial.trial_maker_id == "adaptive_ratings",
    )
)

rows = db.session.execute(statement).mappings()
observations = pd.DataFrame.from_records(rows)
```

When the outcome genuinely represents correctness or participant performance,
use PsyNet's existing scoring interface:

```python
class AccuracyTrial(StaticTrial):
    def score_answer(self, answer, definition):
        return float(answer["selected_option"] == definition["correct_option"])
```

PsyNet saves that result as `trial.score`, so an accuracy model can use it as
its observation. Do not use `score_answer` merely to obtain a convenient
numeric encoding for a rating or choice with no performance interpretation.

Explicit columns are most useful for fields read repeatedly, expensive derived
outcomes, and results of asynchronous processing. Prefer domain-specific names
such as `rating`, `response_time_seconds`, or `estimated_threshold` over a
generic `model_response`.

Create the decision record when selection occurs, not after the participant has
answered. A useful minimum is:

```text
id | participant_id | trial_id | selected_candidate_id
participant_history_count | study_fit_id | candidate_pool_version
selected_utility
```

`participant_history_count` is the number of that participant's finalized
observations used for selection. `study_fit_id` identifies the shared model
snapshot, when there is one. `candidate_pool_version` identifies the item bank
and eligibility rules that produced the candidates. `selected_utility` records
the winning score in the policy's natural units.

A dedicated table makes these fields queryable and gives non-trial decisions a
place to live. Use the suggested `AdaptiveDecision` definition in
`references/study-state-storage.md`, including its relationship to `Trial`.

Create the row in the trial maker's `on_trial_created` hook. PsyNet calls this
after the exact primary trial assignment exists but before the participant sees
it. Repeat trials and synchronized follower copies do not call this hook, so one
adaptive decision row corresponds to one actual policy choice:

```python
class AdaptiveTrialMaker(StaticTrialMaker):
    def on_trial_created(self, trial, experiment, participant, selection_context):
        selected_item_id = trial.definition["item_id"]
        if selection_context["selected_candidate_id"] != selected_item_id:
            raise RuntimeError("Adaptive decision does not match the trial.")
        decision = AdaptiveDecision(
            participant_id=participant.id,
            selected_candidate_id=selected_item_id,
            participant_history_count=selection_context["participant_history_count"],
            study_fit_id=selection_context["study_fit_id"],
            candidate_pool_version=selection_context["candidate_pool_version"],
            selected_utility=selection_context["selected_utility"],
            details=selection_context["details"],
        )
        decision.trial = trial
        db.session.add(decision)
```

Assigning `decision.trial = trial` lets SQLAlchemy populate `trial_id` when the
transaction flushes. The trial and decision are committed or rolled back
together, so do not flush merely to obtain the trial ID.

Use explicit columns for fields needed in routine queries or exports. Keep
`details` small and use it only for genuinely structured diagnostics. Recording
every candidate and utility can be useful for reconstructing a policy, but it
can also be large. Store the full set only when required; otherwise record a
reproducible candidate-pool version and compact summaries.

Finalized responses remain the source of truth for study-level adaptation.
Publish fitted study state as immutable snapshots in a dedicated table, and let
selection use only snapshots marked ready. Small scoring state can live in a
`PythonObject` column; larger state can be stored as an `ExperimentAsset`
referenced by the snapshot. Follow `references/study-state-storage.md` when
implementing this persistence boundary.

Time database loading, model fitting, and candidate scoring separately. Cache
immutable item features and vectorize candidate scoring before changing the
scientific policy. Any shortlist, approximation, or batched update changes the
implemented policy and must be included in planning and simulation.

## Simulate the full procedure
`simulate_procedure.py` should run the adaptive loop without starting PsyNet. It
draws responses from `response_model/`, calls the table-based selection code,
and supports both adaptive and prespecified non-adaptive policies.

Benchmark the adaptive policy against at least one credible non-adaptive
alternative under matched response draws and resource budgets. Evaluate recovery
at prespecified test-length or data-budget checkpoints, including line plots of
the correlation between model estimates and oracle values. Report bias and
error alongside correlation, and separately compare stopping length, exposure,
latency, and other design costs.

Repeat the comparison under plausible misspecification by changing the response
model while leaving the adaptive learner unchanged. Follow
[references/benchmark-adaptive-procedure.md](references/benchmark-adaptive-procedure.md)
for baseline matching, checkpoint metrics, plots, robustness scenarios, and
saved artifacts. Use `power-analysis/SKILL.md` separately to decide whether the
eventual experimental design meets its inferential criterion.

## Validate in PsyNet
Run bots through the adaptive selection path. Use concurrent bots when the
design has shared model state or exposure constraints. Verify from exported
data that decisions use the recorded item-bank or model version and refer
only to finalized observations available at their cutoff. When the policy is
intended to be deterministic, a fixed simulation seed should reproduce the same
selections.
