import inspect
from pathlib import Path

import pytest

from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker
from psynet.trial.dense import DenseTrialMaker
from psynet.trial.main import NetworkTrialMaker, TrialMaker
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 1


class CustomNode(ChainNode):
    pass


class CustomStaticTrial(StaticTrial):
    time_estimate = 1


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


def test_failure_policy_constructor_defaults():
    chain = inspect.signature(ChainTrialMaker.__init__).parameters
    static = inspect.signature(StaticTrialMaker.__init__).parameters
    dense = inspect.signature(DenseTrialMaker.__init__).parameters
    base = inspect.signature(TrialMaker.__init__).parameters
    network = inspect.signature(NetworkTrialMaker.__init__).parameters

    assert chain["fail_trials_on_premature_exit"].default is False
    assert chain["fail_trials_on_participant_performance_check"].default is False
    assert static["fail_trials_on_premature_exit"].default is False
    assert static["fail_trials_on_participant_performance_check"].default is True
    assert dense["fail_trials_on_premature_exit"].default is False
    assert dense["fail_trials_on_participant_performance_check"].default is True
    assert base["fail_trials_on_premature_exit"].default is False
    assert network["fail_trials_on_premature_exit"].default is False

    trial_maker = make_trial_maker()
    assert not trial_maker.fail_trials_on_participant_performance_check
    assert not hasattr(trial_maker, "fail_trials_on_premature_exit")


def test_trial_maker_constructors_are_keyword_only():
    for cls in (TrialMaker, NetworkTrialMaker):
        params = inspect.signature(cls.__init__).parameters
        kinds = [p.kind for name, p in params.items() if name != "self"]
        assert kinds
        assert all(kind is inspect.Parameter.KEYWORD_ONLY for kind in kinds)

    with pytest.raises(TypeError):
        TrialMaker(
            "id",
            object,
            1,
            False,
            False,
            False,
            True,
            "n_trials",
            None,
            0,
            None,
        )

    with pytest.raises(TypeError):
        NetworkTrialMaker(
            "id",
            object,
            object,
            1,
            False,
            False,
            False,
            True,
            "n_trials",
            None,
            0,
            False,
        )


def test_fail_trials_on_premature_exit_true_emits_deprecation_warning():
    with pytest.warns(
        DeprecationWarning, match="fail_trials_on_premature_exit"
    ) as record:
        StaticTrialMaker(
            id_="deprecated_flag",
            trial_class=CustomStaticTrial,
            nodes=[StaticNode(definition={"x": 1})],
            expected_trials_per_participant=1,
            max_trials_per_participant=1,
            recruit_mode="n_trials",
            target_trials_per_node=1,
            fail_trials_on_premature_exit=True,
        )

    warning = record[0]
    assert Path(warning.filename).resolve() == Path(__file__).resolve()


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
