import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait

import pytest
from dallinger import db
from sqlalchemy import Column, Integer, String, UniqueConstraint, text

from psynet.data import SQLBase
from psynet.experiment import Experiment, get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.serialize import SerializedCallback
from psynet.sqlalchemy_profiling import sqlalchemy_profile
from psynet.sync import (
    Barrier,
    BarrierRecord,
    GroupBarrier,
    ParticipantLinkBarrier,
    SimpleGrouper,
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
    def process_potential_releases(self):
        raise RuntimeError("boom")


class RecordingBarrier(Barrier):
    def process_potential_releases(self):
        processed_barriers.append(self.id)


class AutoReleaseBarrier(Barrier):
    def choose_who_to_release(self, waiting_participants):
        processed_barriers.append(self.id)
        return waiting_participants


class SlowLoggingAutoReleaseBarrier(AutoReleaseBarrier):
    def __init__(self, *args, delay=0.02, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay = delay

    def choose_who_to_release(self, waiting_participants):
        time.sleep(self.delay)
        for participant in waiting_participants:
            db.session.add(
                BarrierReleaseEvent(
                    barrier_id=self.id,
                    participant_id=participant.id,
                )
            )
        return super().choose_who_to_release(waiting_participants)


class DummyModel(SQLBase):
    __tablename__ = "dummy_model"

    id = Column(String, primary_key=True)

    def on_release(
        self, group, participants, participant=None, barrier=None, experiment=None
    ):
        return None


class BarrierReleaseEvent(SQLBase):
    __tablename__ = "barrier_release_event"
    __table_args__ = (
        UniqueConstraint(
            "barrier_id",
            "participant_id",
            name="barrier_release_event_once",
        ),
    )

    id = Column(Integer, primary_key=True)
    barrier_id = Column(String, nullable=False)
    participant_id = Column(Integer, nullable=False)


def test_random_partition():
    input = list(range(10))

    with pytest.raises(ValueError):
        SimpleGrouper.randomly_partition_list(input, group_size=3)

    partitioned = SimpleGrouper.randomly_partition_list(input, group_size=2)
    assert len(partitioned) == 5
    contents = [elt for group in partitioned for elt in group]
    assert sorted(contents) == list(range(10))


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
    grouper.process_potential_releases()

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
def test_check_barriers_skips_failure(in_experiment_directory, db_session):
    exp = get_experiment()
    processed_barriers.clear()

    bad_barrier = ExplodingBarrier(id_="a_bad")
    good_barrier = RecordingBarrier(id_="b_good")
    participants = [new_participant(exp) for _ in range(2)]

    bad_barrier.receive_participant(participants[0])
    good_barrier.receive_participant(participants[1])
    db.session.commit()

    exp.check_barriers()

    assert "b_good" in processed_barriers


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_query_count_ignores_inactive_registry_size(
    in_experiment_directory, db_session
):
    """Ensure barrier checks scale with waiting barriers, not registry size."""
    exp = get_experiment()

    def profile_check_barriers(prefix, inactive_barrier_count):
        processed_barriers.clear()

        for i in range(inactive_barrier_count):
            barrier = AutoReleaseBarrier(id_=f"{prefix}_inactive_{i}")
            BarrierRecord.ensure_exists(
                barrier.id,
                barrier.__class__,
                barrier=barrier,
            )

        expected_barrier_ids = [f"{prefix}_waiting_{i}" for i in range(2)]
        for barrier_id in expected_barrier_ids:
            barrier = AutoReleaseBarrier(id_=barrier_id)
            barrier.receive_participant(new_participant(exp))

        db.session.commit()
        db.session.expire_all()

        with sqlalchemy_profile(
            db_session.get_bind(),
            capture_callsite=False,
        ) as profiler:
            exp.check_barriers()

        assert sorted(processed_barriers) == expected_barrier_ids
        return profiler.total_count

    baseline_query_count = profile_check_barriers("baseline", inactive_barrier_count=0)
    inactive_query_count = profile_check_barriers(
        "inactive",
        inactive_barrier_count=50,
    )

    assert inactive_query_count <= baseline_query_count + 2


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_concurrent_workers_release_each_participant_once(
    in_experiment_directory, db_session
):
    """Stress concurrent barrier checks without duplicate participant releases."""
    BarrierReleaseEvent.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    exp = get_experiment()
    prefix = f"stress_{uuid.uuid4().hex}"
    barrier_count = 8
    participants_per_barrier = 3
    worker_count = 4
    start_barrier = threading.Barrier(worker_count)
    barrier_ids = [f"{prefix}_{i}" for i in range(barrier_count)]
    participant_ids = []

    for barrier_id in barrier_ids:
        barrier = SlowLoggingAutoReleaseBarrier(id_=barrier_id)
        for _ in range(participants_per_barrier):
            participant = new_participant(exp)
            barrier.receive_participant(participant)
            db.session.flush()
            participant_ids.append(participant.id)

    db.session.commit()
    db.session.remove()

    def worker():
        db.session.remove()
        try:
            start_barrier.wait(timeout=5)
            db.session.execute(text("SET lock_timeout = '2s'"))
            db.session.execute(text("SET statement_timeout = '10s'"))
            db.session.commit()
            Experiment.check_barriers()
        finally:
            db.session.remove()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(worker) for _ in range(worker_count)]
        done, not_done = wait(futures, timeout=15)
        assert not not_done
        for future in done:
            future.result()

    links = (
        ParticipantLinkBarrier.query.filter(
            ParticipantLinkBarrier.barrier_id.in_(barrier_ids)
        )
        .order_by(ParticipantLinkBarrier.participant_id)
        .all()
    )
    events = (
        BarrierReleaseEvent.query.filter(
            BarrierReleaseEvent.barrier_id.in_(barrier_ids)
        )
        .order_by(BarrierReleaseEvent.participant_id)
        .all()
    )

    assert len(links) == barrier_count * participants_per_barrier
    assert all(link.released for link in links)
    assert all(link.departure_time is not None for link in links)
    assert [event.participant_id for event in events] == sorted(participant_ids)


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
    assert isinstance(barrier.on_release, SerializedCallback)


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
