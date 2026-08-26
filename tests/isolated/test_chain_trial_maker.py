import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from psynet.sync import GroupBarrier
from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker
from psynet.trial.dense import DenseTrialMaker
from psynet.trial.main import NetworkTrialMaker, Trial, TrialMaker
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 1


class CustomNode(ChainNode):
    pass


class CustomStaticTrial(StaticTrial):
    time_estimate = 1


class DummyModuleState:
    def __init__(self):
        self.in_repeat_phase = False


class DummySyncGroup:
    def remove_participant(self, participant):
        participant.active_sync_groups.pop("main", None)


class DummyParticipant:
    def __init__(self):
        self.id = 1
        self.active_sync_groups = {}
        self.branch_log = []
        self.module_state = None
        self.current_trial = None
        self.trial_status = None

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


def test_sync_trial_maker_requires_active_group_for_synced_participant():
    trial_maker = make_trial_maker(sync_group_type="sync")
    participant = DummyParticipant()
    start_switch = next(
        elt
        for elt in trial_maker._init_participant()
        if getattr(elt, "label", None) == "init_participant"
    )

    with pytest.raises(RuntimeError, match="active sync group of type 'sync'"):
        start_switch.get_target(experiment=None, participant=participant)

    assert participant.branch_log == []


def test_trial_sync_group_returns_none_after_kick():
    trial = SimpleNamespace(
        trial_maker=SimpleNamespace(sync_group_type="main"),
        participant=DummyParticipant(),
    )

    assert Trial.sync_group.fget(trial) is None


def test_sync_trial_maker_prepare_barrier_kick_exits_cleanly(monkeypatch):
    trial_maker = make_trial_maker(
        sync_group_type="main",
        sync_group_max_wait_action="kick",
    )
    participant = DummyParticipant()
    participant.module_state = DummyModuleState()
    participant.active_sync_groups["main"] = DummySyncGroup()

    GroupBarrier._kick_participant_after_max_wait(participant, group_type="main")
    assert "main" not in participant.active_sync_groups

    prepare_trial_calls = []

    def fail_if_prepare_trial_called(experiment, participant):
        prepare_trial_calls.append(participant.id)
        raise AssertionError("kicked participants should exit before preparing a trial")

    monkeypatch.setattr(trial_maker, "prepare_trial", fail_if_prepare_trial_called)

    trial_maker._try_to_prepare_trial_solo(experiment=None, participant=participant)

    assert participant.current_trial is None
    assert participant.trial_status == "exit"
    assert prepare_trial_calls == []
