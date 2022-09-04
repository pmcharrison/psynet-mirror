import pytest

from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 5


def new_trial_maker(**kwarg):
    args = dict(
        id_="test_trial_maker",
        node_class=ChainNode,
        trial_class=CustomTrial,
        phase="test",
        chain_type="across",
        num_trials_per_participant=5,
        chains_per_participant=None,
        chains_per_experiment=5,
        trials_per_node=1,
        balance_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        recruit_mode="num_trials",
        target_num_participants=None,
    )
    all_args = {**args, **kwarg}
    return ChainTrialMaker(**all_args)


def test_num_iterations():
    with pytest.deprecated_call():
        tm1 = new_trial_maker(max_nodes_per_chain=10)
        assert tm1.max_nodes_per_chain == 10
        assert tm1.max_nodes_per_chain == 9

    tm2 = new_trial_maker(max_nodes_per_chain=10)
    assert tm2.max_nodes_per_chain == 11

    with pytest.raises(ValueError):
        new_trial_maker(max_nodes_per_chain=10, max_nodes_per_chain=5)
