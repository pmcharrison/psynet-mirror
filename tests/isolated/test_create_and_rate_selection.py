from types import SimpleNamespace

import pytest

from psynet.trial.create_and_rate import (
    CreateAndRateAssignmentPending,
    CreateAndRateTrialMakerMixin,
)


class _Parent:
    def find_chains(self, participant, experiment):
        return self._filter_eligible_candidates(
            list(self._candidates),
            participant,
            experiment,
        )

    def _filter_eligible_candidates(self, chains, participant, experiment):
        return chains


class CreateAndRateSelectionHarness(CreateAndRateTrialMakerMixin, _Parent):
    def __init__(self, candidates, phases, wait_for_networks=False, role=None):
        self._candidates = candidates
        self._phases = phases
        self._role = role
        self.creator_class = "creator"
        self.rater_class = "rater"
        self.wait_for_networks = wait_for_networks
        self.phase_batch_calls = 0

    def get_creation_phases(self, nodes):
        self.phase_batch_calls += 1
        return {node.id: self._phases[node.id] for node in nodes}

    def get_participant_role(self, participant, experiment):
        return self._role


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
        wait_for_networks=True,
    )

    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(node, None, None)
    assert exc_info.value.outcome == "wait"
    assert maker.phase_batch_calls == 1


def test_create_and_rate_pending_assignment_exits_when_wait_is_disabled():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={node.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS},
        wait_for_networks=False,
    )

    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(node, None, None)
    assert exc_info.value.outcome == "exit"


def test_create_and_rate_prepare_trial_maps_pending_assignment_to_wait():
    class Parent:
        def prepare_trial(self, experiment, participant):
            raise CreateAndRateAssignmentPending("wait")

    class Harness(CreateAndRateTrialMakerMixin, Parent):
        def __init__(self):
            self.wait_for_networks = True

    assert Harness().prepare_trial(None, None) == (None, "wait")


def test_participant_role_filters_chains_and_waits_on_phase_flip():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        phases={pending.head.id: CreateAndRateTrialMakerMixin.READY_FOR_RATERS},
        wait_for_networks=True,
        role=CreateAndRateTrialMakerMixin.RATER_ROLE,
    )
    assert maker.find_chains(participant=None, experiment=None) == [pending]
    maker._phases[pending.head.id] = CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS
    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(pending.head, None, None)
    assert exc_info.value.outcome == "wait"


def test_create_and_rate_phase_flip_after_selection_defers_assignment():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={node.id: CreateAndRateTrialMakerMixin.NEEDS_CREATORS},
        wait_for_networks=True,
    )
    assert maker.find_chains(participant=None, experiment=None)[0].head.id == 1
    maker._phases[node.id] = CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS
    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(node, None, None)
    assert exc_info.value.outcome == "wait"


def test_rater_role_keeps_ready_and_waiting_chains():
    pending = chain(1)
    ready = chain(2)
    needs = chain(3)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending, ready, needs],
        phases={
            pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS,
            ready.head.id: CreateAndRateTrialMakerMixin.READY_FOR_RATERS,
            needs.head.id: CreateAndRateTrialMakerMixin.NEEDS_CREATORS,
        },
        wait_for_networks=True,
        role=CreateAndRateTrialMakerMixin.RATER_ROLE,
    )
    assert maker.find_chains(None, None) == [ready]


def test_rater_role_waits_when_only_pending_chains_remain():
    pending = chain(1)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending],
        phases={pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS},
        wait_for_networks=True,
        role=CreateAndRateTrialMakerMixin.RATER_ROLE,
    )
    assert maker.find_chains(participant=None, experiment=None) == "wait"


def test_creator_role_ignores_chains_waiting_to_become_ratable():
    pending = chain(1)
    needs = chain(2)
    maker = CreateAndRateSelectionHarness(
        candidates=[pending, needs],
        phases={
            pending.head.id: CreateAndRateTrialMakerMixin.WAITING_FOR_CREATORS,
            needs.head.id: CreateAndRateTrialMakerMixin.NEEDS_CREATORS,
        },
        wait_for_networks=True,
        role=CreateAndRateTrialMakerMixin.CREATOR_ROLE,
    )

    assert maker.find_chains(None, None) == [needs]


@pytest.mark.parametrize(
    ("role", "phase"),
    [
        (
            CreateAndRateTrialMakerMixin.CREATOR_ROLE,
            CreateAndRateTrialMakerMixin.READY_FOR_RATERS,
        ),
        (
            CreateAndRateTrialMakerMixin.RATER_ROLE,
            CreateAndRateTrialMakerMixin.NEEDS_CREATORS,
        ),
    ],
)
def test_role_phase_mismatch_defers_instead_of_switching_trial_class(role, phase):
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={node.id: phase},
        wait_for_networks=True,
        role=role,
    )

    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(node, None, None)
    assert exc_info.value.outcome == "wait"


def test_invalid_participant_role_is_rejected():
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={1: CreateAndRateTrialMakerMixin.NEEDS_CREATORS},
        role="reviewer",
    )

    with pytest.raises(ValueError, match="get_participant_role"):
        maker.find_chains(None, None)


def test_invalid_participant_role_is_rejected_during_trial_class_resolution():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={1: CreateAndRateTrialMakerMixin.NEEDS_CREATORS},
        role="reviewer",
    )

    with pytest.raises(ValueError, match="get_participant_role"):
        maker.get_trial_class(node, None, None)


def test_role_phase_mismatch_exits_when_wait_is_disabled():
    node = SimpleNamespace(id=1)
    maker = CreateAndRateSelectionHarness(
        candidates=[chain(1)],
        phases={1: CreateAndRateTrialMakerMixin.READY_FOR_RATERS},
        wait_for_networks=False,
        role=CreateAndRateTrialMakerMixin.CREATOR_ROLE,
    )

    with pytest.raises(CreateAndRateAssignmentPending) as exc_info:
        maker.get_trial_class(node, None, None)
    assert exc_info.value.outcome == "exit"


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
