import os
import time
import uuid

import pytest
from dallinger import db
from sqlalchemy import Column, String

from psynet.data import SQLBase
from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.serialize import SerializedCallback
from psynet.sqlalchemy_profiling import sqlalchemy_profile
from psynet.sync import Barrier, BarrierRecord, GroupBarrier, SimpleGrouper

RUN_SYNC_BENCHMARK = os.environ.get("PSYNET_RUN_SYNC_BENCHMARK") == "1"


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


@pytest.mark.skipif(
    not RUN_SYNC_BENCHMARK,
    reason="Set PSYNET_RUN_SYNC_BENCHMARK=1 to run the sync barrier benchmark.",
)
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("consents")], indirect=True
)
def test_check_barriers_benchmark_reports_metrics(in_experiment_directory, db_session):
    """Report barrier-processing metrics without enforcing wall-clock limits."""
    exp = get_experiment()
    processed_barriers.clear()

    prefix = f"benchmark_{uuid.uuid4().hex}"
    barrier_count = 100
    participants_per_barrier = 10
    waiting_barrier_count = 40
    released_barrier_count = 30
    waiting_barrier_ids = []

    for barrier_index in range(barrier_count):
        barrier = AutoReleaseBarrier(id_=f"{prefix}_{barrier_index}")
        is_waiting_barrier = barrier_index < waiting_barrier_count
        is_released_barrier = (
            waiting_barrier_count
            <= barrier_index
            < waiting_barrier_count + released_barrier_count
        )

        for _ in range(participants_per_barrier):
            participant = new_participant(exp)
            barrier.receive_participant(participant)
            db.session.flush()
            if is_released_barrier:
                barrier.release(participant)
            elif not is_waiting_barrier:
                participant.failed = True

        if is_waiting_barrier:
            waiting_barrier_ids.append(barrier.id)

    db.session.commit()
    db.session.expire_all()

    start = time.perf_counter()
    with sqlalchemy_profile(
        db_session.get_bind(),
        capture_callsite=False,
    ) as profiler:
        exp.check_barriers()
    elapsed_seconds = time.perf_counter() - start

    processed_barriers_per_second = len(processed_barriers) / elapsed_seconds
    max_query_duration_ms = max(
        [stat.max_ms for stat in profiler.get_stats()] or [0.0]
    )
    benchmark_summary = (
        "sync barrier benchmark: "
        f"barriers={barrier_count}, "
        f"participant_links={barrier_count * participants_per_barrier}, "
        f"check_barriers_calls=1, "
        f"processed_barriers={len(processed_barriers)}, "
        f"elapsed_seconds={elapsed_seconds:.3f}, "
        f"queries={profiler.total_count}, "
        f"max_query_duration_ms={max_query_duration_ms:.3f}, "
        f"processed_barriers_per_second={processed_barriers_per_second:.1f}"
    )
    print(benchmark_summary)

    assert sorted(processed_barriers) == waiting_barrier_ids


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
