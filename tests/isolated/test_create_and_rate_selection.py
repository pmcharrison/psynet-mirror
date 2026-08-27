from types import SimpleNamespace

import pytest

from psynet.trial.create_and_rate import CreateAndRateTrialMakerMixin


class _Parent:
    def find_chains(self, participant, experiment):
        return list(self._candidates)


class CreateAndRateSelectionHarness(CreateAndRateTrialMakerMixin, _Parent):
    def __init__(self, candidates, phases, wait_for_networks=False):
        self._candidates = candidates
        self._phases = phases
        self.creator_class = "creator"
        self.rater_class = "rater"
        self.wait_for_networks = wait_for_networks
        self.phase_batch_calls = 0

    def get_creation_phases(self, nodes):
        self.phase_batch_calls += 1
        return {node.id: self._phases[node.id] for node in nodes}


def chain(node_id):
    return SimpleNamespace(id=node_id, head=SimpleNamespace(id=node_id))


def test_create_and_rate_assigns_creators_until_slots_are_filled():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={node.id: CreateAndRateTrialMakerMixin.NEEDS_CREATORS},
    )

    assert maker.get_trial_class(node, None, None) == "creator"
    assert maker.phase_batch_calls == 1


def test_create_and_rate_pending_creations_are_not_assignable():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={node.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS},
    )

    with pytest.raises(RuntimeError, match="creator trials to finalize"):
        maker.get_trial_class(node, None, None)
    assert maker.phase_batch_calls == 1


def test_create_and_rate_waits_when_only_pending_chains_remain():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        phases={pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS},
        wait_for_networks=True,
    )

    assert maker.find_chains(participant=None, experiment=None) == "wait"


def test_create_and_rate_exits_when_only_pending_chains_remain_without_wait():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        phases={pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS},
        wait_for_networks=False,
    )

    assert maker.find_chains(participant=None, experiment=None) == "exit"


def test_create_and_rate_returns_assignable_chains():
    pending = chain(1)
    ready = chain(2)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending, ready],
        phases={
            pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS,
            ready.head.id: CreateAndRateTrialMakerMixin.NEEDS_CREATORS,
        },
        wait_for_networks=True,
    )

    assert maker.find_chains(participant=None, experiment=None) == [ready]
    assert maker.phase_batch_calls == 1
