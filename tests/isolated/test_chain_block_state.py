from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker


class CustomTrial(ChainTrial):
    time_estimate = 1


class DummyModuleState:
    def __init__(self, block_order, block_position=0):
        self.block_order = block_order
        self.block_position = block_position
        self.block = block_order[block_position]

    def set_block_position(self, i):
        self.block_position = i
        self.block = self.block_order[i]


class DummyParticipant:
    def __init__(self, module_state, active_sync_groups=None):
        self.module_state = module_state
        self.active_sync_groups = active_sync_groups or {}


class DummyGroup:
    def __init__(self, participants):
        self.participants = participants


def build_trial_maker(sync_group_type=None):
    return ChainTrialMaker(
        id_="tm",
        trial_class=CustomTrial,
        node_class=ChainNode,
        chain_type="across",
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        max_nodes_per_chain=1,
        chains_per_experiment=1,
        balance_across_chains=False,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        recruit_mode="n_participants",
        target_n_participants=1,
        sync_group_type=sync_group_type,
    )


def test_sync_block_state_updates_participant():
    trial_maker = build_trial_maker()
    state = DummyModuleState(["A", "B", "C"])
    participant = DummyParticipant(state)

    trial_maker._sync_block_state(participant, "C")

    assert state.block_position == 2
    assert state.block == "C"


def test_sync_block_state_updates_sync_group():
    trial_maker = build_trial_maker(sync_group_type="sync")
    state_a = DummyModuleState(["A", "B"])
    state_b = DummyModuleState(["A", "B"])
    participant_a = DummyParticipant(state_a)
    participant_b = DummyParticipant(state_b)
    group = DummyGroup([participant_a, participant_b])
    participant_a.active_sync_groups = {"sync": group}
    participant_b.active_sync_groups = {"sync": group}

    trial_maker._sync_block_state(participant_a, "B")

    assert state_a.block_position == 1
    assert state_b.block_position == 1
    assert state_a.block == "B"
    assert state_b.block == "B"
