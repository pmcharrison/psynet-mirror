from types import SimpleNamespace

import pytest

from psynet.trial.create_and_rate import CreateAndRateTrialMakerMixin


class _Parent:
    def find_chains(self, participant, experiment):
        return list(self._candidates)


class CreateAndRateSelectionHarness(CreateAndRateTrialMakerMixin, _Parent):
    def __init__(self, candidates, non_failed, finished, wait_for_networks=False):
        self._candidates = candidates
        self._non_failed = non_failed
        self._finished = finished
        self.n_creators = 2
        self.creator_class = "creator"
        self.rater_class = "rater"
        self.wait_for_networks = wait_for_networks
        self.phase_batch_calls = 0

    def get_non_failed_creations(self, node):
        if isinstance(self._non_failed, dict):
            return self._non_failed[node.id]
        return self._non_failed

    def get_finished_creations(self, node):
        if isinstance(self._finished, dict):
            return self._finished[node.id]
        return self._finished

    def get_creation_phases(self, nodes):
        self.phase_batch_calls += 1
        return {node.id: self._get_creation_phase(node) for node in nodes}


def chain(node_id):
    return SimpleNamespace(id=node_id, head=SimpleNamespace(id=node_id))


def test_create_and_rate_assigns_creators_until_slots_are_filled():
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        non_failed=[object()],
        finished=[],
    )
    node = SimpleNamespace(id=1)

    assert maker.needs_creators(node)
    assert maker.get_trial_class(node, None, None) == "creator"


def test_create_and_rate_pending_creations_are_not_assignable():
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        non_failed=[object(), object()],
        finished=[object()],
    )
    node = SimpleNamespace(id=1)

    assert maker.waiting_for_creators(node)
    with pytest.raises(RuntimeError, match="creator trials to finalize"):
        maker.get_trial_class(node, None, None)


def test_create_and_rate_waits_when_only_pending_chains_remain():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        non_failed=[object(), object()],
        finished=[object()],
        wait_for_networks=True,
    )

    assert maker.find_chains(participant=None, experiment=None) == "wait"


def test_create_and_rate_exits_when_only_pending_chains_remain_without_wait():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        non_failed=[object(), object()],
        finished=[object()],
        wait_for_networks=False,
    )

    assert maker.find_chains(participant=None, experiment=None) == "exit"


def test_create_and_rate_returns_assignable_chains():
    pending = chain(1)
    ready = chain(2)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending, ready],
        non_failed={1: [object(), object()], 2: [object()]},
        finished={1: [object()], 2: []},
        wait_for_networks=True,
    )

    assert maker.find_chains(participant=None, experiment=None) == [ready]
    assert maker.phase_batch_calls == 1
