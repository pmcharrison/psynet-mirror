import pytest

from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker
from psynet.trial.static import StaticTrial, StaticTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 1


class CustomNode(ChainNode):
    pass


class CustomStaticTrial(StaticTrial):
    time_estimate = 1


class DummyParticipant:
    def __init__(self):
        self.active_sync_groups = {}
        self.branch_log = []
        self.module_state = None

    def append_branch_log(self, entry):
        self.branch_log.append(entry)


def make_trial_maker(**kwargs):
    args = dict(
        id_="test_trial_maker",
        node_class=CustomNode,
        trial_class=CustomTrial,
        chain_type="across",
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        chains_per_experiment=1,
        recruit_mode="n_trials",
    )
    return ChainTrialMaker(**{**args, **kwargs})


def test_chain_trial_maker_rejects_mismatched_start_nodes():
    start_nodes = [ChainNode(definition={"seed": "x"})]

    with pytest.raises(ValueError, match="start_nodes must be instances of"):
        make_trial_maker(start_nodes=start_nodes)


def test_chain_trial_maker_rejects_callable_start_nodes_with_mismatch():
    def start_nodes():
        return [ChainNode(definition={"seed": "x"})]

    trial_maker = make_trial_maker(start_nodes=start_nodes)

    with pytest.raises(ValueError, match="start_nodes must be instances of"):
        trial_maker.resolve_start_nodes()


def test_static_trial_maker_error_mentions_nodes():
    nodes = [ChainNode(definition={"seed": "x"})]

    with pytest.raises(ValueError, match="nodes must be instances of StaticNode"):
        StaticTrialMaker(
            id_="test_static_trial_maker",
            trial_class=CustomStaticTrial,
            nodes=nodes,
            expected_trials_per_participant=1,
            max_trials_per_participant=1,
            recruit_mode="n_trials",
            target_trials_per_node=1,
        )


def test_sync_trial_maker_initializes_participant_without_active_group():
    trial_maker = make_trial_maker(sync_group_type="sync")
    participant = DummyParticipant()
    start_switch = next(
        elt
        for elt in trial_maker._init_participant()
        if getattr(elt, "label", None) == "init_participant"
    )

    assert (
        start_switch.get_target(experiment=None, participant=participant)
        is (start_switch.targets[False])
    )
    assert participant.branch_log == [["init_participant", False]]
