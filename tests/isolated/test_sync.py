import json
import threading
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from dallinger import db
from dallinger.models import timenow
from sqlalchemy import Column, String, text
from sqlalchemy.exc import OperationalError

from psynet.dashboard.sync_groups import (
    _fail_sync_group_participant,
    _get_grouper_progress,
    _index_waiting_barriers,
    _kick_sync_group_participant,
    _summarize_waiting_at_barriers,
)
from psynet.data import SQLBase
from psynet.db import transaction
from psynet.experiment import Experiment, get_experiment
from psynet.page import WaitPage
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.serialize import SerializedCallable
from psynet.sync import (
    Barrier,
    BarrierDefinition,
    BarrierInstance,
    GroupBarrier,
    SimpleGrouper,
    SimpleSyncGroup,
    _run_pending_barrier_checks,
    _take_pending_barrier_checks,
    check_barriers,
    check_sync_groups,
    pending_arrival_notice_for,
)
from psynet.timeline_hold import (
    TimelineHoldRecord,
    _enqueue_timeline_hold_wake,
    _timeline_hold_channel,
    default_group_barrier_arrival_message,
)


def get_random_id():
    return str(uuid.uuid4())


def new_participant(experiment):
    participant = Participant(
        experiment=experiment,
        recruiter_id="hotair",
        worker_id=get_random_id(),
        hit_id="XYZ",
        assignment_id=get_random_id(),
        mode="debug",
    )
    db.session.add(participant)
    return participant


processed_barriers = []
two_poller_checks = []
two_poller_check_started = threading.Event()
two_poller_check_can_finish = threading.Event()


class ExplodingBarrier(Barrier):
    def check_waiting_participants(self, waiting_participants):
        raise RuntimeError("boom")

    def choose_who_to_release(self, waiting_participants):
        return []


class RecordingBarrier(Barrier):
    def check_waiting_participants(self, waiting_participants):
        processed_barriers.append(self.id)

    def choose_who_to_release(self, waiting_participants):
        return []


class ReleaseAllBarrier(Barrier):
    def choose_who_to_release(self, waiting_participants):
        return waiting_participants


class BlockingReleaseBarrier(ReleaseAllBarrier):
    def check_waiting_participants(self, waiting_participants):
        two_poller_checks.append(self.id)
        two_poller_check_started.set()
        assert two_poller_check_can_finish.wait(timeout=2)


class WaitForTwoBarrier(Barrier):
    def choose_who_to_release(self, waiting_participants):
        if len(waiting_participants) < 2:
            return []
        return waiting_participants


class ConfigurableBarrier(Barrier):
    def __init__(self, id_, required):
        super().__init__(id_)
        self.required = required

    def choose_who_to_release(self, waiting_participants):
        if len(waiting_participants) < self.required:
            return []
        return waiting_participants


class RecordingTimeoutGroupBarrier(GroupBarrier):
    def handle_max_wait_timeout(self, participant):
        participant.timeout_callback_ran = True


class DummyModel(SQLBase):
    __tablename__ = "dummy_model"

    id = Column(String, primary_key=True)

    def on_release(
        self, group, participants, participant=None, barrier=None, experiment=None
    ):
        group.var.callback_owner = self.id


def test_random_partition():
    input = list(range(10))

    with pytest.raises(ValueError):
        SimpleGrouper.randomly_partition_list(input, group_size=3)

    partitioned = SimpleGrouper.randomly_partition_list(input, group_size=2)
    assert len(partitioned) == 5
    contents = [elt for group in partitioned for elt in group]
    assert sorted(contents) == list(range(10))


def test_max_wait_action_kick_requires_group_barrier():
    with pytest.raises(TypeError, match="max_wait_action"):
        Barrier(id_="plain_barrier", max_wait_action="kick")

    with pytest.raises(TypeError, match="max_wait_action"):
        RecordingBarrier(id_="recording_barrier", max_wait_action="kick")

    barrier = GroupBarrier(
        id_="group_barrier",
        group_type="main",
        max_wait_action="kick",
    )
    assert barrier.max_wait_action == "kick"


def test_group_barrier_preserves_positional_timeout_arguments():
    barrier = GroupBarrier(
        "group_barrier",
        "main",
        None,
        3,
        20,
        "fail",
        None,
        False,
        5,
        "kick",
    )

    assert barrier.timeout_between_barriers_time == 5
    assert barrier.timeout_between_barriers_action == "kick"
    assert barrier.expected_wait == 1.5


def test_default_barrier_uses_timeline_hold():
    barrier = ReleaseAllBarrier(id_="hold")

    assert barrier.waiting_logic.is_timeline_hold
    assert barrier.waiting_logic.barrier_id == barrier.id
    assert barrier.waiting_logic.time_estimate == 1.5
    assert barrier.waiting_logic.content is None
    assert barrier.waiting_logic.message_kind == "barrier"
    assert not isinstance(barrier.waiting_logic, WaitPage)


def test_barrier_accepts_custom_hold_content():
    barrier = GroupBarrier(
        id_="wait_for_partner",
        group_type="pair",
        content="Waiting for your partner",
    )
    hold = barrier.waiting_logic

    assert hold.content == "Waiting for your partner"
    assert hold.message_kind is None
    assert hold.translated_content() == "Waiting for your partner"


def test_explicit_barrier_waiting_logic_is_preserved():
    waiting_logic = WaitPage(wait_time=1)
    barrier = ReleaseAllBarrier(id_="page_wait", waiting_logic=waiting_logic)

    assert barrier.waiting_logic is waiting_logic


def test_expected_wait_rejects_explicit_waiting_logic():
    with pytest.raises(ValueError, match="expected_wait"):
        ReleaseAllBarrier(
            id_="page_wait",
            waiting_logic=WaitPage(wait_time=1),
            expected_wait=2,
        )


def test_content_rejects_explicit_waiting_logic():
    with pytest.raises(ValueError, match="content"):
        ReleaseAllBarrier(
            id_="page_wait",
            waiting_logic=WaitPage(wait_time=1),
            content="Waiting for your partner",
        )


def test_barrier_rejects_negative_expected_wait():
    with pytest.raises(ValueError, match="expected_wait"):
        ReleaseAllBarrier(id_="negative_wait", expected_wait=-1)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_barrier_definition_and_instance_use_request_transaction(
    in_experiment_directory, db_session
):
    """Barrier persistence must not commit through a hidden side session."""
    participant = new_participant(get_experiment())
    participant.status = "working"
    barrier = ReleaseAllBarrier(id_=f"transactional_{get_random_id()}")

    barrier.receive_participant(participant)
    definition_id = barrier.id
    instance_id = participant.active_barriers[barrier.id].barrier_instance_id

    with db.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT id FROM barrier WHERE id = :id"),
                {"id": definition_id},
            ).first()
            is None
        )
        assert (
            connection.execute(
                text("SELECT id FROM barrier_instance WHERE id = :id"),
                {"id": instance_id},
            ).first()
            is None
        )

    db_session.commit()
    assert BarrierDefinition.query.get(definition_id) is not None
    assert BarrierInstance.query.get(instance_id) is not None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_pending_barrier_checks_are_discarded_on_rollback(
    in_experiment_directory, db_session
):
    participant = new_participant(get_experiment())
    participant.status = "working"
    barrier = ReleaseAllBarrier(id_="rolled_back_arrival")
    _arrive_at_group_barrier(get_experiment(), barrier, participant)

    db_session.rollback()

    assert _take_pending_barrier_checks() == []


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_reuses_one_instance_per_group_visit(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first, second = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(id_="instance_visit", group_type="main")

    _arrive_at_group_barrier(exp, barrier, first)
    first_instance_id = first.active_barriers[barrier.id].barrier_instance_id
    _commit_barrier_arrivals()
    _arrive_at_group_barrier(exp, barrier, second)
    second_instance_id = second.barrier_links[-1].barrier_instance_id
    _commit_barrier_arrivals()

    assert second_instance_id == first_instance_id
    assert not BarrierInstance.query.get(first_instance_id).active

    barrier.receive_participant(first)
    next_instance_id = first.active_barriers[barrier.id].barrier_instance_id
    assert next_instance_id != first_instance_id


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_existing_barrier_instance_does_not_take_creation_lock(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    first, second = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(id_="instance_fast_path", group_type="main")
    barrier.receive_participant(first)
    db_session.commit()

    def reject_creation_lock(instance_id, *, wait=False):
        if wait:
            raise AssertionError("Existing instances must not take the creation lock.")
        return True

    monkeypatch.setattr("psynet.sync._claim_barrier_instance", reject_creation_lock)
    barrier.receive_participant(second)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_barrier_id_rejects_a_different_class(in_experiment_directory, db_session):
    exp = get_experiment()
    first = new_participant(exp)
    second = new_participant(exp)
    first.status = second.status = "working"
    ReleaseAllBarrier(id_="stable_definition").receive_participant(first)
    db_session.commit()

    with pytest.raises(ValueError, match="already identifies"):
        WaitForTwoBarrier(id_="stable_definition").receive_participant(second)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_shared_barrier_id_rejects_different_behavior(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first = new_participant(exp)
    second = new_participant(exp)
    first.status = second.status = "working"
    ConfigurableBarrier(id_="stable_behavior", required=2).receive_participant(first)
    db_session.commit()

    with pytest.raises(ValueError, match="different behavior"):
        ConfigurableBarrier(id_="stable_behavior", required=3).receive_participant(
            second
        )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_same_group_barrier_id_uses_distinct_instances_per_group(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first_group = _pair_sync_group(exp, db_session)[0]
    second_group = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(id_="group_scoped", group_type="main")

    barrier.receive_participant(first_group[0])
    barrier.receive_participant(second_group[0])

    first_instance = first_group[0].active_barriers[barrier.id].barrier_instance
    second_instance = second_group[0].active_barriers[barrier.id].barrier_instance
    assert first_instance.id != second_instance.id
    assert first_instance.group_id != second_instance.group_id
    assert first_instance.participant_links == [
        first_group[0].active_barriers[barrier.id]
    ]
    assert second_instance.participant_links == [
        second_group[0].active_barriers[barrier.id]
    ]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_same_barrier_id_keeps_each_group_visits_callback(
    in_experiment_directory, db_session
):
    """Each group's instance must retain its first arrival's bound callback."""
    DummyModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    exp = get_experiment()
    first_group, first_sync_group = _pair_sync_group(exp, db_session)
    second_group, second_sync_group = _pair_sync_group(exp, db_session)
    first_owner = DummyModel(id=get_random_id())
    second_owner = DummyModel(id=get_random_id())
    db_session.add_all([first_owner, second_owner])
    db_session.flush()
    first_barrier = GroupBarrier(
        id_="callback_scoped", group_type="main", on_release=first_owner.on_release
    )
    second_barrier = GroupBarrier(
        id_="callback_scoped", group_type="main", on_release=second_owner.on_release
    )

    _arrive_at_group_barrier(exp, first_barrier, first_group[0])
    _arrive_at_group_barrier(exp, second_barrier, second_group[0])
    _commit_barrier_arrivals()
    _arrive_at_group_barrier(exp, first_barrier, first_group[1])
    _arrive_at_group_barrier(exp, second_barrier, second_group[1])
    _commit_barrier_arrivals()

    db_session.refresh(first_sync_group)
    db_session.refresh(second_sync_group)
    assert first_sync_group.var.callback_owner == first_owner.id
    assert second_sync_group.var.callback_owner == second_owner.id


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_accepts_same_callback_bound_to_each_participants_model(
    in_experiment_directory, db_session
):
    """Participant-local ORM receivers must not change shared barrier behavior."""
    DummyModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    exp = get_experiment()
    participants, sync_group = _pair_sync_group(exp, db_session)
    owners = [DummyModel(id=get_random_id()), DummyModel(id=get_random_id())]
    db_session.add_all(owners)
    db_session.flush()

    for participant, owner in zip(participants, owners):
        barrier = GroupBarrier(
            id_="participant_bound_callback",
            group_type="main",
            on_release=owner.on_release,
        )
        _arrive_at_group_barrier(exp, barrier, participant)

    _commit_barrier_arrivals()
    db_session.refresh(sync_group)
    assert sync_group.var.callback_owner == owners[0].id


def test_group_barrier_resolved_timeout_uses_overridden_handler():
    barrier = RecordingTimeoutGroupBarrier(
        id_="group_barrier",
        group_type="main",
        max_wait_action="kick",
    )
    elts = barrier.resolve()
    hold = next(elt for elt in elts if getattr(elt, "is_timeline_hold", False))
    participant = SimpleNamespace(timeout_callback_ran=False, module_state=None)

    assert hold.fail_on_timeout is False
    hold.apply_timeout(participant)
    assert participant.timeout_callback_ran


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_allocator(in_experiment_directory, db_session):
    exp = get_experiment()
    grouper = SimpleGrouper(group_type="main", initial_group_size=3)
    participants = [new_participant(exp) for _ in range(6)]

    _arrive_at_group_barrier(exp, grouper, participants[0])
    _commit_barrier_arrivals()

    assert BarrierDefinition.query.get("main_grouper") is not None
    assert "main_grouper" in participants[0].active_barriers
    assert "main_grouper" not in participants[1].active_barriers
    assert not grouper.can_participant_exit(participants[0])

    for participant in participants:
        assert participant.sync_group is None

    _arrive_at_group_barrier(exp, grouper, participants[1])
    _commit_barrier_arrivals()

    assert not grouper.can_participant_exit(participants[0])

    for participant in participants:
        assert participant.sync_group is None

    _arrive_at_group_barrier(exp, grouper, participants[2])

    _commit_barrier_arrivals()

    assert grouper.can_participant_exit(participants[0])

    for participant in participants[:3]:
        group = participant.sync_group
        assert len(group.participants) == 3
        assert group.creation_time is not None
        assert group.end_time is None

    group = participants[0].sync_group
    assert isinstance(group.leader, Participant)

    with pytest.raises(TypeError, match=r"group\.add_participant"):
        group.participants.append(participants[3])
    assert participants[3] not in group.participants

    with pytest.raises(
        RuntimeError,
        match="Participant is already in a group with this group_type \\('main'\\).",
    ):
        grouper.receive_participant(participants[0])

    group.close()
    db.session.commit()

    assert participants[0].sync_group is None
    grouper.receive_participant(participants[0])


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_simple_grouper_groups_on_last_arrival(in_experiment_directory, db_session):
    exp = get_experiment()
    first, second = [new_participant(exp) for _ in range(2)]
    for participant in (first, second):
        participant.status = "working"
    grouper = SimpleGrouper(
        group_type="pair_on_arrival",
        initial_group_size=2,
        content="Waiting for your partner",
    )

    _arrive_at_group_barrier(exp, grouper, first)
    _commit_barrier_arrivals()
    assert first.sync_group is None

    _arrive_at_group_barrier(exp, grouper, second)
    _commit_barrier_arrivals()
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.sync_group is not None
    assert second.sync_group.id == first.sync_group.id
    assert len(first.sync_group.participants) == 2


def test_sync_group_dashboard_waiting_barrier_indexes():
    waiting_by_participant, waiting_by_barrier = _index_waiting_barriers(
        [
            (2, "barrier_b"),
            (1, "barrier_a"),
            (2, "barrier_a"),
        ]
    )

    assert waiting_by_participant[1] == ["barrier_a"]
    assert waiting_by_participant[2] == ["barrier_b", "barrier_a"]
    assert waiting_by_barrier == {
        "barrier_a": (2, [1, 2]),
        "barrier_b": (1, [2]),
    }
    assert _summarize_waiting_at_barriers({1, 2}, waiting_by_participant) == [
        {"barrier_id": "barrier_a", "waiting_count": 2, "participant_ids": [1, 2]},
        {"barrier_id": "barrier_b", "waiting_count": 1, "participant_ids": [2]},
    ]


def test_sync_group_dashboard_grouper_progress_uses_timeline_all_elts(monkeypatch):
    grouper = SimpleGrouper(group_type="main", initial_group_size=3, batch_size=2)
    timeline = SimpleNamespace(
        all_elts=[
            SimpleNamespace(links={"barrier": grouper}),
            SimpleNamespace(links={"barrier": grouper}),
            SimpleNamespace(links={}),
        ]
    )
    monkeypatch.setattr(
        "psynet.experiment.get_experiment",
        lambda: SimpleNamespace(timeline=timeline),
    )

    assert _get_grouper_progress() == [
        {
            "barrier_id": "main_grouper",
            "group_type": "main",
            "batch_size": 2,
            "initial_group_size": 3,
        }
    ]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_manual_sync_group_participant_failure(in_experiment_directory, db_session):
    exp = get_experiment()
    participants = [new_participant(exp) for _ in range(2)]
    for participant in participants:
        participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=2,
        max_group_size=2,
        min_group_size=1,
        n_active_participants=2,
        accepts_top_ups=False,
    )
    db_session.add(group)
    for participant in participants:
        group.add_participant(participant)
    group.leader = participants[0]
    db_session.commit()

    failed_participant = _fail_sync_group_participant(
        participants[0].id, group.id, "manual_failure"
    )

    assert failed_participant.failed
    assert "manual_failure" in failed_participant.failure_tags
    assert participants[0] not in group.active_participants
    assert participants[1] in group.active_participants


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_manual_sync_group_participant_kick(in_experiment_directory, db_session):
    exp = get_experiment()
    participants = [new_participant(exp) for _ in range(2)]
    for participant in participants:
        participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=2,
        max_group_size=2,
        min_group_size=1,
        n_active_participants=2,
        accepts_top_ups=False,
    )
    db_session.add(group)
    for participant in participants:
        group.add_participant(participant)
    group.leader = participants[0]
    db_session.commit()

    kicked_participant = _kick_sync_group_participant(
        participants[0].id, group.id, "manual_kick"
    )

    assert not kicked_participant.failed
    assert "manual_failure" not in kicked_participant.failure_tags
    assert participants[0] not in group.active_participants
    assert participants[1] in group.active_participants


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_manual_sync_group_participant_kick_targets_selected_group(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"

    main_group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=2,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=True,
    )
    secondary_group = SimpleSyncGroup(
        group_type="secondary",
        initial_group_size=1,
        max_group_size=2,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=True,
    )
    db_session.add(main_group)
    db_session.add(secondary_group)
    main_group.add_participant(participant)
    secondary_group.add_participant(participant)
    main_group.leader = participant
    secondary_group.leader = participant
    db_session.commit()

    kicked_participant = _kick_sync_group_participant(
        participant.id, secondary_group.id, "manual_kick"
    )

    assert kicked_participant == participant
    assert participant in main_group.active_participants
    assert participant not in secondary_group.active_participants
    assert participant.active_sync_groups == {"main": main_group}


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_manual_sync_group_participant_kick_handles_empty_top_up_group(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=2,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=True,
    )
    db_session.add(group)
    group.add_participant(participant)
    group.leader = participant
    db_session.commit()

    kicked_participant = _kick_sync_group_participant(
        participant.id, group.id, "manual_kick"
    )

    assert not kicked_participant.failed
    assert group.active_participants == []
    assert group.n_active_participants == 0
    assert group.leader is None
    assert group.active


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
@pytest.mark.parametrize("fail_below_min_size", [True, False])
def test_manual_sync_group_participant_kick_dissolves_group_below_min_size(
    in_experiment_directory, db_session, fail_below_min_size
):
    exp = get_experiment()
    participants = [new_participant(exp) for _ in range(3)]
    for participant in participants:
        participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=3,
        n_active_participants=3,
        accepts_top_ups=False,
        fail_participants_below_min_size=fail_below_min_size,
    )
    db_session.add(group)
    for participant in participants:
        group.add_participant(participant)
    group.leader = participants[0]
    db_session.commit()

    kicked_participant = _kick_sync_group_participant(
        participants[0].id, group.id, "manual_kick"
    )

    assert not kicked_participant.failed
    assert participants[0] not in group.active_participants
    assert participants[1] not in group.active_participants
    assert participants[2] not in group.active_participants
    assert participants[1].failed == fail_below_min_size
    assert participants[2].failed == fail_below_min_size
    assert group.n_active_participants == 0
    assert not group.active


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
@pytest.mark.parametrize("participant_status", ["approved", "returned"])
def test_manual_sync_group_participant_failure_rejects_non_working_participants(
    in_experiment_directory, db_session, participant_status
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = participant_status

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=False,
    )
    db_session.add(group)
    group.add_participant(participant)
    group.leader = participant
    db_session.commit()

    with pytest.raises(
        ValueError, match="Only active working participants can be failed manually."
    ):
        _fail_sync_group_participant(participant.id, group.id, "manual_failure")

    assert not participant.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_manual_sync_group_participant_failure_rejects_inactive_group_member(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=False,
    )
    db_session.add(group)
    group.add_participant(participant)
    group.participant_links[0].active = False
    group.leader = participant
    db_session.commit()

    with pytest.raises(
        ValueError, match="not currently active in the selected sync group"
    ):
        _fail_sync_group_participant(participant.id, group.id, "manual_failure")

    assert not participant.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_skips_failure(in_experiment_directory, db_session):
    exp = get_experiment()
    processed_barriers.clear()

    bad_barrier = ExplodingBarrier(id_="a_bad")
    good_barrier = RecordingBarrier(id_="b_good")
    participants = [new_participant(exp) for _ in range(2)]

    bad_barrier.receive_participant(participants[0])
    good_barrier.receive_participant(participants[1])
    db.session.commit()

    check_barriers()

    assert "b_good" in processed_barriers


_group_release_calls = []


def _count_group_release(
    group, participants, participant=None, barrier=None, experiment=None
):
    _group_release_calls.append(group.id)


def _custom_arrival_message(*, kind, waiting_count=None, group_size=None, **kwargs):
    return "custom"


def _sync_group_of(exp, db_session, n, group_type="main"):
    participants = [new_participant(exp) for _ in range(n)]
    for participant in participants:
        participant.status = "working"
    group = SimpleSyncGroup(
        group_type=group_type,
        initial_group_size=n,
        max_group_size=n,
        min_group_size=n,
        n_active_participants=n,
        accepts_top_ups=False,
    )
    db_session.add(group)
    for participant in participants:
        group.add_participant(participant)
    group.leader = participants[0]
    db_session.commit()
    return participants, group


def _pair_sync_group(exp, db_session, group_type="main"):
    return _sync_group_of(exp, db_session, 2, group_type)


def _arrive_at_group_barrier(exp, barrier, participant):
    barrier.receive_participant(participant)
    if barrier._uses_timeline_hold:
        barrier.waiting_logic.consume(exp, participant)


def _commit_barrier_arrivals():
    """Mirror the response route's write and coordination commits."""
    db.session.commit()
    checks = _take_pending_barrier_checks()
    if checks:
        _run_pending_barrier_checks(checks)
        db.session.commit()


def _barrier_link_released(participant_id, barrier_id):
    with db.engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT released
                FROM participant_link_barrier
                WHERE participant_id = :participant_id
                  AND barrier_id = :barrier_id
                """
            ),
            {"participant_id": participant_id, "barrier_id": barrier_id},
        ).scalar()


def _participant_row_is_locked(participant_id):
    """Return whether another connection holds ``FOR UPDATE`` on this participant."""
    with db.engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(
                text("SELECT id FROM participant WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": participant_id},
            )
        except OperationalError as err:
            if getattr(getattr(err, "orig", None), "pgcode", None) == "55P03":
                return True
            raise
        else:
            return False
        finally:
            trans.rollback()


def test_finalize_barrier_arrivals_commits_checks_before_participant_relock(
    monkeypatch,
):
    """Barrier-wide participant locks must not span timeline advancement."""
    events = []
    participant = SimpleNamespace(id=1)

    class Page:
        def __json__(self, participant):
            return {"participant_id": participant.id}

    page = Page()

    class Query:
        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def get(self, participant_id):
            events.append("participant_relock")
            assert events == ["check", "commit", "participant_relock"]
            return participant

    experiment = SimpleNamespace(
        _participant_request_query=lambda: Query(),
        _advance_past_ready_holds=lambda participant, current_page: current_page,
        timeline=SimpleNamespace(get_current_elt=lambda experiment, participant: page),
    )
    result = SimpleNamespace(page=None, payload={})

    monkeypatch.setattr(
        "psynet.experiment._set_transaction_lock_timeout", lambda seconds: None
    )
    monkeypatch.setattr(
        "psynet.sync._run_pending_barrier_checks",
        lambda checks: events.append("check") or True,
    )
    monkeypatch.setattr("psynet.sync._take_pending_barrier_checks", lambda: [])
    monkeypatch.setattr(db.session, "commit", lambda: events.append("commit"))

    Experiment._finalize_barrier_arrivals(
        experiment,
        participant_id=1,
        checks=["instance"],
        result=result,
    )

    assert events == ["check", "commit", "participant_relock", "commit"]
    assert result.page is page
    assert result.payload["page"] == {"participant_id": 1}


def test_finalize_barrier_arrivals_does_not_relock_after_losing_claim(monkeypatch):
    """A peer that owns the check may keep participant rows locked."""
    events = []
    participant = SimpleNamespace(id=1)

    class Query:
        def with_for_update(self, **kwargs):
            events.append("participant_relock")
            return self

        def get(self, participant_id):
            events.append("participant_read")
            return participant

    experiment = SimpleNamespace(_participant_request_query=lambda: Query())
    result = SimpleNamespace(page=object(), payload={"page": "hold"})

    monkeypatch.setattr(
        "psynet.experiment._set_transaction_lock_timeout", lambda seconds: None
    )
    monkeypatch.setattr(
        "psynet.sync._run_pending_barrier_checks",
        lambda checks: events.append("check") or False,
    )
    monkeypatch.setattr(db.session, "commit", lambda: events.append("commit"))

    returned = Experiment._finalize_barrier_arrivals(
        experiment,
        participant_id=1,
        checks=["instance"],
        result=result,
    )

    assert returned is participant
    assert events == ["check", "commit", "participant_read"]
    assert result.payload == {"page": "hold"}


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_skips_locked_waiters_and_continues(
    in_experiment_directory, db_session
):
    """A participant write must not block other barriers in the same poller sweep."""
    exp = get_experiment()
    locked_barrier = ReleaseAllBarrier(id_="a_locked")
    free_barrier = ReleaseAllBarrier(id_="b_free")
    locked_participant = new_participant(exp)
    free_participant = new_participant(exp)
    locked_participant.status = "working"
    free_participant.status = "working"
    locked_barrier.receive_participant(locked_participant)
    free_barrier.receive_participant(free_participant)
    db.session.commit()
    locked_id = locked_participant.id
    free_id = free_participant.id

    with db.engine.connect() as conn:
        trans = conn.begin()
        conn.execute(
            text("SELECT id FROM participant WHERE id = :id FOR UPDATE"),
            {"id": locked_id},
        )
        check_barriers()
        locked_released = _barrier_link_released(locked_id, "a_locked")
        free_released = _barrier_link_released(free_id, "b_free")
        trans.rollback()

    assert locked_released is False
    assert free_released is True

    check_barriers()
    assert _barrier_link_released(locked_id, "a_locked") is True


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_two_pollers_process_one_barrier_instance_once(
    in_experiment_directory, db_session
):
    participant = new_participant(get_experiment())
    participant.status = "working"
    BlockingReleaseBarrier(id_="single_claim").receive_participant(participant)
    db_session.commit()
    two_poller_checks.clear()
    two_poller_check_started.clear()
    two_poller_check_can_finish.clear()
    errors = []

    def run_poller():
        try:
            check_barriers()
        except Exception as err:  # pragma: no cover - surfaced below
            errors.append(err)
        finally:
            db.session.remove()

    first = threading.Thread(target=run_poller, daemon=True)
    second = threading.Thread(target=run_poller, daemon=True)
    first.start()
    assert two_poller_check_started.wait(timeout=2)
    second.start()
    second.join(timeout=2)
    two_poller_check_can_finish.set()
    first.join(timeout=2)

    assert errors == []
    assert not first.is_alive()
    assert not second.is_alive()
    assert two_poller_checks == ["single_claim"]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_arrival_does_not_wait_for_poller_metadata_lock(
    in_experiment_directory, db_session
):
    """A blocked poller must not prevent another group entering the barrier."""
    import threading
    import time

    exp = get_experiment()
    blocked_participants, blocked_group = _pair_sync_group(exp, db_session)
    arriving_participants, _ = _pair_sync_group(exp, db_session)
    barrier = GroupBarrier(id_="independent_claim", group_type="main")
    for participant in blocked_participants:
        barrier.receive_participant(participant)
    db_session.commit()

    poller_pid = []
    poller_errors = []

    def run_poller():
        try:
            poller_pid.append(
                db.session.execute(text("SELECT pg_backend_pid()")).scalar()
            )
            check_barriers()
        except Exception as err:  # pragma: no cover - surfaced below
            poller_errors.append(err)
        finally:
            db.session.remove()

    with db.engine.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(
            text(
                """
                UPDATE sync_group
                SET last_barrier_pass_time = :timestamp
                WHERE id = :group_id
                """
            ),
            {"timestamp": timenow(), "group_id": blocked_group.id},
        )

        poller = threading.Thread(target=run_poller, daemon=True)
        poller.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if poller_pid:
                blocked = blocker.execute(
                    text(
                        """
                        SELECT cardinality(pg_blocking_pids(:pid)) > 0
                        """
                    ),
                    {"pid": poller_pid[0]},
                ).scalar()
                if blocked:
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("Poller did not block on the held sync-group row.")

        started = time.perf_counter()
        barrier.receive_participant(arriving_participants[0])
        db_session.flush()
        elapsed = time.perf_counter() - started
        transaction.rollback()

    poller.join(timeout=2)
    assert elapsed < 1
    assert poller_errors == []
    assert not poller.is_alive()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_last_group_arrival_releases_without_poller(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    participants, group = _pair_sync_group(exp, db_session)
    first, last = participants
    group_id = group.id
    _group_release_calls.clear()
    barrier = GroupBarrier(
        id_="last_arrival",
        group_type="main",
        on_release=_count_group_release,
    )
    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda channel_name, data: publications.append(
            (channel_name, json.loads(data))
        ),
    )

    _arrive_at_group_barrier(exp, barrier, first)
    first_wake = first.timeline_holds[0].wake_token
    _commit_barrier_arrivals()
    assert barrier.id in first.active_barriers
    assert not barrier.waiting_logic.participant_can_resume(exp, first)
    assert _group_release_calls == []

    _arrive_at_group_barrier(exp, barrier, last)
    last_wake = last.timeline_holds[0].wake_token
    assert not barrier.waiting_logic.participant_can_resume(exp, last)
    _commit_barrier_arrivals()

    assert barrier.id not in first.active_barriers
    assert barrier.id not in last.active_barriers
    assert _group_release_calls == [group_id]
    assert barrier.waiting_logic.participant_can_resume(exp, last)
    release_targets = [
        target
        for _, payload in publications
        for target in payload["targets"]
        if target.get("reason") == "barrier_released"
    ]
    wake_tokens = {target["wake_token"] for target in release_targets}
    assert first_wake in wake_tokens
    assert last_wake in wake_tokens

    check_barriers()
    assert _group_release_calls == [group_id]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_last_arrival_does_not_keep_partner_rows_locked(
    in_experiment_directory, db_session
):
    """Arrival defers waiter locking until after the write transaction commits."""
    exp = get_experiment()
    participants, _group = _pair_sync_group(exp, db_session)
    first, last = participants
    barrier = GroupBarrier(id_="release_partner_locks", group_type="main")

    _arrive_at_group_barrier(exp, barrier, first)
    _commit_barrier_arrivals()
    first_id = first.id
    last_id = last.id

    _arrive_at_group_barrier(exp, barrier, last)

    assert not _participant_row_is_locked(first_id)
    assert _participant_row_is_locked(last_id)
    _commit_barrier_arrivals()
    assert not _participant_row_is_locked(first_id)
    assert not _participant_row_is_locked(last_id)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_last_group_arrival_releases_explicit_waiting_logic_without_poller(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first, last = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(
        id_="last_arrival_page",
        group_type="main",
        waiting_logic=WaitPage(wait_time=1),
    )

    barrier.receive_participant(first)
    _commit_barrier_arrivals()
    assert barrier.id in first.active_barriers

    barrier.receive_participant(last)
    _commit_barrier_arrivals()

    assert barrier.id not in first.active_barriers
    assert barrier.id not in last.active_barriers


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_last_group_arrival_defers_when_a_partner_is_locked(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first, last = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(id_="locked_partner", group_type="main")
    _arrive_at_group_barrier(exp, barrier, first)
    _commit_barrier_arrivals()
    first_id = first.id
    last_id = last.id

    with db.engine.connect() as conn:
        trans = conn.begin()
        conn.execute(
            text("SELECT id FROM participant WHERE id = :id FOR UPDATE"),
            {"id": first_id},
        )
        _arrive_at_group_barrier(exp, barrier, last)
        _commit_barrier_arrivals()
        assert _barrier_link_released(first_id, "locked_partner") is False
        assert _barrier_link_released(last_id, "locked_partner") is False
        trans.rollback()

    check_barriers()
    assert _barrier_link_released(first_id, "locked_partner") is True
    assert _barrier_link_released(last_id, "locked_partner") is True


def test_default_group_barrier_arrival_message_copy():
    assert (
        default_group_barrier_arrival_message(
            kind="hold", waiting_count=1, group_size=2
        )
        is None
    )
    assert (
        default_group_barrier_arrival_message(
            kind="hold", waiting_count=1, group_size=3
        )
        == "2 of 3 not ready yet"
    )
    assert (
        default_group_barrier_arrival_message(
            kind="hold", waiting_count=2, group_size=3
        )
        == "1 of 3 not ready yet"
    )
    assert (
        default_group_barrier_arrival_message(
            kind="hold", waiting_count=3, group_size=3
        )
        is None
    )
    assert (
        default_group_barrier_arrival_message(
            kind="notice", waiting_count=1, group_size=2
        )
        == "Your partner is ready."
    )
    assert (
        default_group_barrier_arrival_message(
            kind="notice", waiting_count=1, group_size=3
        )
        == "1/3 of your group are ready."
    )
    assert (
        default_group_barrier_arrival_message(
            kind="notice", waiting_count=2, group_size=3
        )
        == "2/3 of your group are ready."
    )


def test_group_barrier_notify_arrivals_defaults_on():
    barrier = GroupBarrier(id_="default_notice", group_type="main")
    assert barrier.notify_arrivals is True

    quiet = GroupBarrier(id_="quiet_notice", group_type="main", notify_arrivals=False)
    assert quiet.notify_arrivals is False


def test_on_arrival_message_enables_notify_arrivals():
    barrier = GroupBarrier(
        id_="custom_notice",
        group_type="main",
        on_arrival_message=_custom_arrival_message,
    )
    assert barrier.notify_arrivals is True
    assert (
        barrier._call_arrival_message(
            kind="notice", waiting_count=1, group_size=2, recipient=None, group=None
        )
        == "custom"
    )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_arrival_notifies_partner_still_on_earlier_page(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    first, last = _pair_sync_group(exp, db_session)[0]
    barrier = GroupBarrier(
        id_="notify_arrivals",
        group_type="main",
        content="Waiting for your partner",
    )
    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda channel_name, data: publications.append(
            (channel_name, json.loads(data))
        ),
    )

    _arrive_at_group_barrier(exp, barrier, first)
    db_session.commit()

    notices = [
        target.get("notice")
        for _, payload in publications
        for target in payload["targets"]
    ]
    hold_messages = [
        target.get("hold_message")
        for _, payload in publications
        for target in payload["targets"]
    ]
    assert "Your partner is ready." in notices
    assert all(
        not message or "psynet-timeline-hold-progress" not in message
        for message in hold_messages
    )
    assert pending_arrival_notice_for(last) == "Your partner is ready."
    overlay = barrier.waiting_logic.overlay_html(first)
    assert "Waiting for your partner" in overlay
    assert "psynet-timeline-hold-progress" not in overlay


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_hold_reports_how_many_are_not_ready_yet(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    first, second, third = _sync_group_of(exp, db_session, 3)[0]
    barrier = GroupBarrier(
        id_="group_hold_remaining",
        group_type="main",
        content="Waiting for the rest of your group",
    )

    _arrive_at_group_barrier(exp, barrier, first)
    db_session.commit()
    overlay = barrier.waiting_logic.overlay_html(first)
    assert "2 of 3 not ready yet" in overlay
    assert pending_arrival_notice_for(second) == "1/3 of your group are ready."
    assert pending_arrival_notice_for(third) == "1/3 of your group are ready."

    _arrive_at_group_barrier(exp, barrier, second)
    db_session.commit()
    overlay = barrier.waiting_logic.overlay_html(first)
    assert "1 of 3 not ready yet" in overlay
    assert pending_arrival_notice_for(third) == "2/3 of your group are ready."


def _group_n_active(group_id):
    with db.engine.connect() as conn:
        return conn.execute(
            text("SELECT n_active_participants FROM sync_group WHERE id = :id"),
            {"id": group_id},
        ).scalar()


def test_scheduled_check_sync_groups_uses_experiment_override(monkeypatch):
    calls = []
    experiment = SimpleNamespace(
        check_sync_groups=lambda: calls.append("experiment override")
    )
    monkeypatch.setattr("psynet.experiment.is_experiment_launched", lambda: True)
    monkeypatch.setattr("psynet.experiment.get_experiment", lambda: experiment)
    monkeypatch.setattr(
        "psynet.sync.check_sync_groups", lambda: calls.append("module default")
    )

    Experiment._check_sync_groups()

    assert calls == ["experiment override"]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_sync_groups_does_not_commit_callers_transaction(
    in_experiment_directory, db_session
):
    DummyModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)

    with transaction(commit=False):
        db_session.add(DummyModel(id="unrelated-write"))
        Experiment.check_sync_groups()

    assert DummyModel.query.get("unrelated-write") is None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_sync_groups_skips_locked_group_and_continues(
    in_experiment_directory, db_session
):
    """A participant write that holds a group must not stall recounting others."""
    exp = get_experiment()
    locked_participant = new_participant(exp)
    free_participant = new_participant(exp)
    locked_participant.status = "working"
    free_participant.status = "working"

    locked_group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=99,
        accepts_top_ups=False,
    )
    free_group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=99,
        accepts_top_ups=False,
    )
    db_session.add_all([locked_group, free_group])
    locked_group.add_participant(locked_participant)
    free_group.add_participant(free_participant)
    locked_group.leader = locked_participant
    free_group.leader = free_participant
    db_session.commit()
    locked_id = locked_group.id
    free_id = free_group.id

    with db.engine.connect() as conn:
        trans = conn.begin()
        conn.execute(
            text("SELECT id FROM sync_group WHERE id = :id FOR UPDATE"),
            {"id": locked_id},
        )
        check_sync_groups()
        locked_count = _group_n_active(locked_id)
        free_count = _group_n_active(free_id)
        trans.rollback()

    assert locked_count == 99
    assert free_count == 1

    check_sync_groups()
    assert _group_n_active(locked_id) == 1


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_publishes_release_after_commit(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"
    participant.page_uuid = "hold-page-uuid"
    barrier = ReleaseAllBarrier(id_="release_all")
    barrier.receive_participant(participant)
    hold = TimelineHoldRecord(
        participant=participant,
        page_uuid=participant.page_uuid,
        hold_id="barrier:release_all",
        started_at=timenow(),
        expected_wait=1.5,
        max_wait_time=20,
        fix_time_credit=False,
        actual_wait_seconds=0,
        credited_wait_seconds=0,
    )
    participant.active_barriers[barrier.id].timeline_hold = hold
    db_session.add(hold)
    db_session.commit()
    participant_id = participant.id
    barrier_id = barrier.id
    wake_token = hold.wake_token

    publications = []

    def publish(channel_name, data):
        with db.engine.connect() as connection:
            released, released_at = connection.execute(
                text(
                    """
                    SELECT participant_link_barrier.released,
                           timeline_hold.released_at
                    FROM participant_link_barrier
                    JOIN timeline_hold
                      ON timeline_hold.id =
                         participant_link_barrier.timeline_hold_id
                    WHERE participant_link_barrier.participant_id = :participant_id
                      AND participant_link_barrier.barrier_id = :barrier_id
                    """
                ),
                {
                    "participant_id": participant_id,
                    "barrier_id": barrier_id,
                },
            ).one()
        assert released
        assert released_at is not None
        publications.append((json.loads(data), channel_name))

    monkeypatch.setattr(db.redis_conn, "publish", publish)

    check_barriers()

    assert publications == [
        (
            {
                "type": "timeline_hold_wake",
                "targets": [
                    {
                        "wake_token": wake_token,
                        "reason": "barrier_released",
                    }
                ],
            },
            _timeline_hold_channel(participant_id),
        )
    ]
    assert not db_session().in_transaction()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_timeline_hold_wake_is_discarded_on_rollback(
    in_experiment_directory, db_session, monkeypatch
):
    participant = new_participant(get_experiment())
    participant.page_uuid = "rolled-back"
    hold = TimelineHoldRecord(
        participant=participant,
        page_uuid=participant.page_uuid,
        hold_id="rollback",
        started_at=timenow(),
        expected_wait=1,
        max_wait_time=20,
        fix_time_credit=False,
    )
    db_session.add(hold)
    db_session.flush()
    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda *args, **kwargs: publications.append((args, kwargs)),
    )

    _enqueue_timeline_hold_wake(participant.id, page_uuid="rolled-back")
    db_session.rollback()
    db_session.commit()

    assert publications == []


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_shared_barrier_id_preserves_each_visit_waiting_mode(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    held_participant, page_participant = [new_participant(exp) for _ in range(2)]
    for participant in [held_participant, page_participant]:
        participant.status = "working"

    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda channel_name, data: publications.append(json.loads(data)),
    )

    held_barrier = WaitForTwoBarrier(id_="shared")
    held_barrier.receive_participant(held_participant)
    held_barrier.waiting_logic.consume(exp, held_participant)
    page_barrier = WaitForTwoBarrier(id_="shared", waiting_logic=WaitPage(wait_time=1))
    page_barrier.receive_participant(page_participant)
    held_wake_token = held_participant.timeline_holds[0].wake_token
    _commit_barrier_arrivals()

    release_targets = [
        target
        for payload in publications
        for target in payload["targets"]
        if target.get("reason") == "barrier_released"
    ]
    assert [target["wake_token"] for target in release_targets] == [held_wake_token]
    assert all("page_uuid" not in target for target in release_targets)

    check_barriers()
    assert [
        target["wake_token"]
        for payload in publications
        for target in payload["targets"]
        if target.get("reason") == "barrier_released"
    ] == [held_wake_token]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_barrier_hold_releases_link_before_pending_redirect(
    in_experiment_directory, db_session
):
    participant = new_participant(get_experiment())
    participant.status = "working"
    participant.page_uuid = "redirect-hold"
    barrier = ReleaseAllBarrier(id_="redirect")
    barrier.receive_participant(participant)
    hold_page = barrier.waiting_logic
    hold_page.consume(get_experiment(), participant)
    participant.pending_redirect = "unsuccessful_end"

    hold_page.prepare_to_resume(participant)

    assert participant.barrier_links[0].released
    assert participant.barrier_links[0].timeline_hold.released_at is not None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_barrier_hold_creates_new_record_after_resume(
    in_experiment_directory, db_session
):
    participant = new_participant(get_experiment())
    participant.status = "working"
    barrier = ReleaseAllBarrier(id_="new_loop")
    barrier.receive_participant(participant)
    hold_page = barrier.waiting_logic
    hold_page.consume(get_experiment(), participant)
    first_record = participant.active_barriers[barrier.id].timeline_hold
    assert first_record.deadline_at is not None
    hold_page.account_wait(participant, settle=True)

    hold_page.consume(get_experiment(), participant)
    db_session.flush()

    assert (
        TimelineHoldRecord.query.filter_by(participant_id=participant.id).count() == 2
    )
    assert participant.active_barriers[barrier.id].timeline_hold is not first_record


def test_group_barrier_rejects_bound_method():
    class Dummy:
        def handler(
            self, group, participants
        ):  # pragma: no cover - used for validation
            return None

    with pytest.raises(ValueError, match="module-level"):
        GroupBarrier(id_="bad", group_type="group", on_release=Dummy().handler)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_accepts_orm_instance_method(in_experiment_directory, db_session):
    DummyModel.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    instance = DummyModel(id=get_random_id())
    db_session.add(instance)
    db_session.flush()

    barrier = GroupBarrier(
        id_="orm_method",
        group_type="group",
        on_release=instance.on_release,
    )
    assert isinstance(barrier.on_release, SerializedCallable)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_barrier_registry_strips_waiting_logic(db_session):
    barrier = GroupBarrier(id_="strip_wait", group_type="group")
    barrier_definition = BarrierDefinition(
        id=barrier.id, barrier_class=barrier.__class__
    )
    barrier_instance = BarrierInstance(
        id=get_random_id(),
        definition=barrier_definition,
        group_id=None,
        active=True,
        barrier=barrier.for_registry(),
    )
    db_session.add(barrier_instance)
    db_session.commit()

    loaded = BarrierInstance.query.get(barrier_instance.id)
    assert loaded.barrier.waiting_logic is None


def test_group_barrier_timeout_between_barriers_rejects_bad_action():
    with pytest.raises(ValueError, match="timeout_between_barriers_action"):
        GroupBarrier(
            id_="timeout_between_barriers_bad_action",
            group_type="group",
            timeout_between_barriers_time=5,
            timeout_between_barriers_action="remove",
        )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_timeout_between_barriers_kick_missing_participants(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    barrier = GroupBarrier(
        id_="timeout_between_barriers_kick",
        group_type="main",
        timeout_between_barriers_time=5,
        timeout_between_barriers_action="kick",
    )

    # Create 3 participants in the same sync group, but only 2 "reach" this barrier.
    participants = [new_participant(exp) for _ in range(3)]
    for p in participants:
        p.status = "working"
    waiting_participants = participants[:2]
    missing_participant = participants[2]

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=2,
        n_active_participants=3,
        accepts_top_ups=False,
        fail_participants_below_min_size=True,
    )
    group.last_barrier_pass_time = timenow() - timedelta(seconds=10)
    db_session.add(group)
    for p in participants:
        group.add_participant(p)
    db_session.commit()

    barrier.check_waiting_participants(waiting_participants)
    released = barrier.choose_who_to_release(waiting_participants)

    assert missing_participant not in group.active_participants
    assert missing_participant not in released
    assert set(released) == set(waiting_participants)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_timeout_between_barriers_kick_releases_waiters_after_dissolution(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    barrier = GroupBarrier(
        id_="timeout_between_barriers_kick_below_min",
        group_type="main",
        timeout_between_barriers_time=5,
        timeout_between_barriers_action="kick",
    )

    participants = [new_participant(exp) for _ in range(3)]
    for p in participants:
        p.status = "working"
    waiting_participants = participants[:2]
    missing_participant = participants[2]

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=3,
        n_active_participants=3,
        accepts_top_ups=False,
        fail_participants_below_min_size=False,
    )
    group.last_barrier_pass_time = timenow() - timedelta(seconds=10)
    db_session.add(group)
    for p in participants:
        group.add_participant(p)
    db_session.commit()

    barrier.check_waiting_participants(waiting_participants)
    released = barrier.choose_who_to_release(waiting_participants)

    assert group.active_participants == []
    assert missing_participant not in released
    assert set(released) == set(waiting_participants)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_timeout_between_barriers_fail_missing_participants(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    barrier = GroupBarrier(
        id_="timeout_between_barriers_fail",
        group_type="main",
        timeout_between_barriers_time=5,
        timeout_between_barriers_action="fail",
    )

    participants = [new_participant(exp) for _ in range(3)]
    for p in participants:
        p.status = "working"
    waiting_participants = participants[:2]
    missing_participant = participants[2]

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=2,
        n_active_participants=3,
        accepts_top_ups=False,
        fail_participants_below_min_size=True,
    )
    group.last_barrier_pass_time = timenow() - timedelta(seconds=10)
    db_session.add(group)
    for p in participants:
        group.add_participant(p)
    db_session.commit()

    barrier.check_waiting_participants(waiting_participants)
    released = barrier.choose_who_to_release(waiting_participants)

    assert missing_participant.failed is True
    assert missing_participant not in group.active_participants
    assert set(released) == set(waiting_participants)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
@pytest.mark.parametrize("fail_below_min_size", [True, False])
def test_group_barrier_fail_participants_below_min_size(
    in_experiment_directory, db_session, fail_below_min_size
):
    exp = get_experiment()
    barrier = GroupBarrier(
        id_="fail_participants_below_min_size",
        group_type="main",
    )

    participants = [new_participant(exp) for _ in range(2)]
    for p in participants:
        p.status = "working"

    # Configure group so it's below min size and doesn't accept top-ups.
    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=3,
        n_active_participants=2,
        accepts_top_ups=False,
        fail_participants_below_min_size=fail_below_min_size,
    )
    group.last_barrier_pass_time = timenow()
    db_session.add(group)
    for p in participants:
        group.add_participant(p)
    db_session.commit()

    released = barrier.choose_who_to_release(waiting_participants=participants)

    assert set(released) == set(participants)
    assert group.active_participants == []
    assert all(p.active_sync_groups.get("main") is None for p in participants)
    assert all(p.failed == fail_below_min_size for p in participants)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_below_min_size_only_releases_waiting_participants(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    barrier = GroupBarrier(
        id_="below_min_size_partial_wait",
        group_type="main",
    )

    waiting_participant = new_participant(exp)
    non_waiting_participant = new_participant(exp)
    for participant in [waiting_participant, non_waiting_participant]:
        participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=3,
        max_group_size=3,
        min_group_size=3,
        n_active_participants=2,
        accepts_top_ups=False,
        fail_participants_below_min_size=True,
    )
    db_session.add(group)
    group.add_participant(waiting_participant)
    group.add_participant(non_waiting_participant)
    db_session.commit()

    released = barrier.choose_who_to_release(waiting_participants=[waiting_participant])

    assert released == [waiting_participant]
    assert waiting_participant.failed
    assert non_waiting_participant.failed
    assert group.active_participants == []


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_participant_kick(in_experiment_directory, db_session):
    participant = Participant(
        experiment=get_experiment(),
        recruiter_id="hotair",
        worker_id=str(uuid.uuid4()),
        hit_id="XYZ",
        assignment_id=str(uuid.uuid4()),
        mode="debug",
    )
    participant.status = "working"
    db_session.add(participant)

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=False,
        fail_participants_below_min_size=True,
    )
    db_session.add(group)
    group.add_participant(participant)
    db_session.commit()

    assert "main" in participant.active_sync_groups
    GroupBarrier._kick_participant_after_max_wait(
        participant=participant, group_type="main"
    )
    db_session.commit()

    assert participant.active_sync_groups.get("main") is None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_group_barrier_max_wait_kick_releases_barrier_link(
    in_experiment_directory, db_session
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"

    group = SimpleSyncGroup(
        group_type="main",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=1,
        accepts_top_ups=False,
        fail_participants_below_min_size=True,
    )
    db_session.add(group)
    group.add_participant(participant)

    barrier = GroupBarrier(
        id_="max_wait_kick",
        group_type="main",
        max_wait_action="kick",
    )
    barrier.receive_participant(participant)
    db_session.commit()

    assert "main" in participant.active_sync_groups
    assert "max_wait_kick" in participant.active_barriers

    barrier.handle_max_wait_timeout(participant)
    db_session.commit()

    assert participant.active_sync_groups.get("main") is None
    assert "max_wait_kick" not in participant.active_barriers
    assert not participant.failed
