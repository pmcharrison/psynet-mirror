# Adapt an existing static node bank

Use this reference when adaptation reorders a fixed bank of authored nodes and
you want PsyNet's balancing, blocks, and participant groups. When the adaptive
unit is a combination of stored objects, or when the candidate set is large,
prefer `Trial.cue` as described in the main skill.

## Rank the eligible nodes

Override `select_node`, and wrap the result in `Selection` when you write a
decision row:

```python
from psynet.trial.main import Selection

class AdaptiveTrialMaker(StaticTrialMaker):
    def select_node(self, nodes, participant, experiment):
        nodes_by_item_id = {node.definition["item_id"]: node for node in nodes}
        utilities = adaptive_logic.score_available_items(
            study_state=latest_ready_snapshot().state,
            candidate_items=ITEMS.loc[list(nodes_by_item_id)],
            participant=participant_row(participant),
        )
        selected_item_id = utilities.idxmax()
        return Selection(
            value=nodes_by_item_id[selected_item_id],
            context={"selected_candidate_id": selected_item_id},
        )
```

PsyNet calls `select_node` only when at least one eligible node exists. The rest
of the contract is strict, which is another reason not to push a large or
combinatorial policy through it:

- Return one of the objects in `nodes`, or a `Selection` wrapping it. A
  re-queried node with the same database ID raises `ValueError`. `select_chain`
  behaves the same way.
- `select_node` cannot return `None`, `[]`, `"wait"`, or `"exit"`. To wait for a
  model refresh or to end the trial maker, override `find_nodes`, call
  `super()`, then filter or return `"wait"` / `"exit"`.
- Eligibility belongs in `custom_node_filter` and ranking in `select_node`.
  Repeat suppression already comes from `allow_repeated_nodes=False`; combine it
  with `n_repeat_trials=0` when an item must never recur. Use
  `custom_node_filter` with a stable item ID when several nodes represent the
  same logical item.
- Chain makers use `find_chains`, `custom_chain_filter`, and `select_chain`. Do
  not override the managed `prepare_trial` of a `NetworkTrialMaker`.
- `Selection.context` lives only for the current trial-construction call.
  Returning a bare node gives `selection_context=None` in `on_trial_created`,
  which is where the decision row is written.

## Stop a participant early

Adapt `should_finish_block`, keeping the criterion itself in
`adaptive_logic.py` so the standalone simulation calls the same function:

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
