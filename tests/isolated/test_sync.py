import uuid

import pytest
from dallinger import db

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo
from psynet.sync import SimpleGrouper


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


def test_random_partition():
    input = list(range(10))

    with pytest.raises(ValueError):
        SimpleGrouper.randomly_partition_list(input, group_size=3)

    partitioned = SimpleGrouper.randomly_partition_list(input, group_size=2)
    assert len(partitioned) == 5
    contents = [elt for group in partitioned for elt in group]
    assert sorted(contents) == list(range(10))


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("consents")], indirect=True
)
def test_group_allocator(in_experiment_directory, db_session):
    exp = get_experiment()
    grouper = SimpleGrouper(group_type="main", group_size=3)
    participants = [new_participant(exp) for _ in range(6)]

    assert len(grouper.get_waiting_participants()) == 0

    grouper.receive_participant(participants[0])
    db.session.commit()

    assert len(grouper.get_waiting_participants()) == 1
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
    db.session.commit()

    grouper.process_potential_releases()

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
