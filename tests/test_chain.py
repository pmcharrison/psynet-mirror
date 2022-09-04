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
        expected_trials_per_participant=5,
        max_trials_per_participant=5,
        chains_per_participant=None,
        chains_per_experiment=5,
        trials_per_node=1,
        balance_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        recruit_mode="n_trials",
        target_n_participants=None,
    )
    all_args = {**args, **kwarg}
    return ChainTrialMaker(**all_args)
