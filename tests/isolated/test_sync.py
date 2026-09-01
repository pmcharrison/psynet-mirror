import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from dallinger import db
from dallinger.models import timenow
from sqlalchemy import Column, String, text

from psynet.dashboard.sync_groups import (
    _fail_sync_group_participant,
    _get_grouper_progress,
    _index_waiting_barriers,
    _kick_sync_group_participant,
    _summarize_waiting_at_barriers,
)
from psynet.data import SQLBase
from psynet.experiment import get_experiment
from psynet.page import WaitPage
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.serialize import SerializedCallable
from psynet.sync import (
    Barrier,
    BarrierRecord,
    GroupBarrier,
    SimpleGrouper,
    SimpleSyncGroup,
    check_barriers,
    check_sync_groups,
)
from psynet.timeline_hold import (
    TimelineHoldRecord,
    _enqueue_timeline_hold_wake,
    _timeline_hold_channel,
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


class ExplodingBarrier(Barrier):
    def check(self):
        raise RuntimeError("boom")


class RecordingBarrier(Barrier):
    def check(self):
        processed_barriers.append(self.id)


class ReleaseAllBarrier(Barrier):
    def choose_who_to_release(self, waiting_participants):
        return waiting_participants


class OverridingReleaseBarrier(Barrier):
    def check(self):
        for participant in self.get_waiting_participants(for_update=True):
            self.release(participant)


class RecordingTimeoutGroupBarrier(GroupBarrier):
    def handle_max_wait_timeout(self, participant):
        participant.timeout_callback_ran = True


class DummyModel(SQLBase):
    __tablename__ = "dummy_model"

    id = Column(String, primary_key=True)

    def on_release(
        self, group, participants, participant=None, barrier=None, experiment=None
    ):
        return None


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
def test_barrier_record_ensure_exists_commits_independently(
    in_experiment_directory, db_session
):
    """Registry inserts must be visible before the caller's transaction commits.

    Concurrent /timeline requests previously blocked on ``barrier.id`` while the
    first participant kept the insert open through HTML rendering.
    """
    barrier_id = f"autonomous_{get_random_id()}"
    barrier = ReleaseAllBarrier(id_=barrier_id)

    BarrierRecord.ensure_exists(barrier_id, type(barrier), barrier)

    # Another connection must see the row even if this session rolls back.
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM barrier WHERE id = :id"),
            {"id": barrier_id},
        ).first()
    assert row is not None

    db.session.rollback()
    db.session.expire_all()
    assert BarrierRecord.query.get(barrier_id) is not None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_concurrent_barrier_ensure_exists_does_not_block(
    in_experiment_directory, db_session
):
    """Two threads inserting the same barrier id must both finish promptly."""
    import threading
    import time

    barrier_id = f"concurrent_{get_random_id()}"
    barrier = ReleaseAllBarrier(id_=barrier_id)
    start = threading.Barrier(2)
    errors = []
    elapsed_ms = []

    def worker():
        try:
            start.wait(timeout=5)
            began = time.perf_counter()
            BarrierRecord.ensure_exists(barrier_id, type(barrier), barrier)
            elapsed_ms.append((time.perf_counter() - began) * 1000)
        except Exception as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert len(elapsed_ms) == 2
    assert max(elapsed_ms) < 1000
    assert BarrierRecord.query.get(barrier_id) is not None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_existing_barrier_refresh_does_not_lock_caller_transaction(
    in_experiment_directory, db_session
):
    """Refreshing registry metadata must not lock through request rendering."""
    import threading
    import time

    barrier_id = f"existing_{get_random_id()}"
    barrier = ReleaseAllBarrier(id_=barrier_id)
    BarrierRecord.ensure_exists(barrier_id, type(barrier), barrier)
    holder_ready = threading.Event()
    release_holder = threading.Event()
    elapsed = []
    errors = []

    def holder():
        try:
            BarrierRecord.ensure_exists(barrier_id, type(barrier), barrier)
            db.session.flush()
            holder_ready.set()
            release_holder.wait(timeout=5)
            db.session.rollback()
        except Exception as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)
        finally:
            db.session.remove()

    def peer():
        try:
            holder_ready.wait(timeout=5)
            began = time.perf_counter()
            BarrierRecord.ensure_exists(barrier_id, type(barrier), barrier)
            db.session.flush()
            elapsed.append(time.perf_counter() - began)
            db.session.rollback()
        except Exception as exc:  # pragma: no cover - surfaced via errors
            errors.append(exc)
        finally:
            release_holder.set()
            db.session.remove()

    threads = [threading.Thread(target=target) for target in [holder, peer]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert len(elapsed) == 1
    assert elapsed[0] < 1


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

    assert len(grouper.get_waiting_participants()) == 0

    grouper.receive_participant(participants[0])
    db.session.commit()

    assert len(grouper.get_waiting_participants()) == 1
    assert BarrierRecord.query.get("main_grouper") is not None
    assert "main_grouper" in participants[0].active_barriers
    assert "main_grouper" not in participants[1].active_barriers
    assert not grouper.can_participant_exit(participants[0])

    for participant in participants:
        assert participant.sync_group is None

    grouper.receive_participant(participants[1])
    db.session.commit()

    assert len(grouper.get_waiting_participants()) == 2
    assert not grouper.can_participant_exit(participants[0])

    for participant in participants:
        assert participant.sync_group is None

    grouper.receive_participant(participants[2])
    grouper.check()

    db.session.commit()

    assert grouper.can_participant_exit(participants[0])
    assert len(grouper.get_waiting_participants()) == 0

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


def test_waiting_participants_nowait_requires_for_update():
    with pytest.raises(ValueError, match="nowait"):
        Barrier.get_waiting_participants_from_barrier_id(
            "x", for_update=False, nowait=True
        )


def _group_n_active(group_id):
    with db.engine.connect() as conn:
        return conn.execute(
            text("SELECT n_active_participants FROM sync_group WHERE id = :id"),
            {"id": group_id},
        ).scalar()


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
def test_overridden_barrier_check_still_publishes_hold_wake(
    in_experiment_directory, db_session, monkeypatch
):
    exp = get_experiment()
    participant = new_participant(exp)
    participant.status = "working"
    participant.page_uuid = "override-hold"
    barrier = OverridingReleaseBarrier(id_="override")
    barrier.receive_participant(participant)
    hold = TimelineHoldRecord(
        participant=participant,
        page_uuid=participant.page_uuid,
        hold_id="barrier:override",
        started_at=timenow(),
        expected_wait=1.5,
        max_wait_time=20,
        fix_time_credit=False,
    )
    participant.active_barriers[barrier.id].timeline_hold = hold
    db_session.add(hold)
    db_session.commit()
    wake_token = hold.wake_token

    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda channel_name, data: publications.append(json.loads(data)),
    )

    check_barriers()

    assert publications[0]["targets"][0]["wake_token"] == wake_token


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

    held_barrier = ReleaseAllBarrier(id_="shared")
    held_barrier.receive_participant(held_participant)
    held_barrier.waiting_logic.consume(exp, held_participant)
    page_barrier = ReleaseAllBarrier(id_="shared", waiting_logic=WaitPage(wait_time=1))
    page_barrier.receive_participant(page_participant)
    db_session.commit()
    held_wake_token = held_participant.timeline_holds[0].wake_token

    publications = []
    monkeypatch.setattr(
        db.redis_conn,
        "publish",
        lambda channel_name, data: publications.append(json.loads(data)),
    )

    check_barriers()

    targets = publications[0]["targets"]
    assert [target["wake_token"] for target in targets] == [held_wake_token]
    assert all("page_uuid" not in target for target in targets)


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
    barrier_record = BarrierRecord(
        id=barrier.id,
        barrier_class=barrier.__class__,
        barrier=barrier.for_registry(),
    )
    db_session.add(barrier_record)
    db_session.commit()

    loaded = BarrierRecord.query.get("strip_wait")
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
    assert barrier.get_waiting_participants() == []
    assert not participant.failed
