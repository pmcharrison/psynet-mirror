import pytest

from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 1


class CustomNode(ChainNode):
    pass


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
