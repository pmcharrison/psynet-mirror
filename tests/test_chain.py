import pytest

from psynet.trial.chain import (
    ChainNetwork,
    ChainNode,
    ChainSource,
    ChainTrial,
    ChainTrialMaker,
)


class CustomTrial(ChainTrial):
    time_estimate = 5


def new_trial_maker(**kwarg):
    args = dict(
        id_="test_trial_maker",
        network_class=ChainNetwork,
        node_class=ChainNode,
        source_class=ChainSource,
        trial_class=CustomTrial,
        phase="test",
        chain_type="across",
        num_trials_per_participant=5,
        num_chains_per_participant=None,
        num_chains_per_experiment=5,
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
        tm1 = new_trial_maker(num_nodes_per_chain=10)
        assert tm1.num_nodes_per_chain == 10
        assert tm1.num_iterations_per_chain == 9

    tm2 = new_trial_maker(num_iterations_per_chain=10)
    assert tm2.num_nodes_per_chain == 11

    with pytest.raises(ValueError):
        new_trial_maker(num_nodes_per_chain=10, num_iterations_per_chain=5)
