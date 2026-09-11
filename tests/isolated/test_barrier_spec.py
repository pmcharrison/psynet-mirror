import json

import pytest

from psynet.barrier_spec import (
    BarrierSpecError,
    barrier_from_spec_json,
    barrier_spec_json,
    behavior_hash,
)
from psynet.sync import Barrier, GroupBarrier, GroupCloser, SimpleGrouper


class ThresholdBarrier(Barrier):
    def __init__(self, id_, threshold):
        super().__init__(id_)
        self.threshold = threshold

    def choose_who_to_release(self, waiting_participants):
        if len(waiting_participants) < self.threshold:
            return []
        return waiting_participants


def on_release(group, participants):
    group.released_count = len(participants)


def test_custom_barrier_round_trip_uses_plain_json():
    original = ThresholdBarrier("threshold", threshold=2)

    serialized = barrier_spec_json(original)
    restored = barrier_from_spec_json(serialized)
    spec = json.loads(serialized)

    assert spec["class"] == "test_barrier_spec.ThresholdBarrier"
    assert spec["state"] == {"id": "threshold", "threshold": 2}
    assert spec["version"] == 1
    assert spec["presentation"]["content"] is None
    assert spec["page_policy"]["_uses_timeline_hold"] is True
    assert "waiting_logic" not in spec["state"]
    assert isinstance(restored, ThresholdBarrier)
    assert restored.id == "threshold"
    assert restored.threshold == 2
    assert restored.content is None
    assert restored.waiting_logic is None
    assert restored._uses_timeline_hold is True


def test_callback_round_trip():
    original = GroupBarrier(
        "callback",
        group_type="pair",
        on_release=on_release,
    )

    restored = barrier_from_spec_json(barrier_spec_json(original))

    assert restored.group_type == "pair"
    assert restored.on_release.function is on_release


@pytest.mark.parametrize(
    "original",
    [
        SimpleGrouper(group_type="pair", initial_group_size=2),
        GroupCloser(group_type="pair"),
    ],
)
def test_built_in_barrier_round_trip(original):
    restored = barrier_from_spec_json(barrier_spec_json(original))

    assert type(restored) is type(original)
    assert restored.id == original.id
    assert behavior_hash(restored) == behavior_hash(original)


def test_behavior_hash_tracks_release_state():
    first = ThresholdBarrier("threshold", threshold=2)
    same = ThresholdBarrier("threshold", threshold=2)
    different = ThresholdBarrier("threshold", threshold=3)

    assert behavior_hash(first) == behavior_hash(same)
    assert behavior_hash(first) != behavior_hash(different)


def test_invalid_spec_version_is_rejected():
    serialized = json.dumps(
        {
            "version": 99,
            "class": "test_barrier_spec.ThresholdBarrier",
            "state": {"id": "threshold", "threshold": 2},
        }
    )

    with pytest.raises(BarrierSpecError, match="version"):
        barrier_from_spec_json(serialized)


def test_unsupported_state_is_rejected():
    barrier = ThresholdBarrier("threshold", threshold=2)
    barrier.unsupported = object()

    with pytest.raises(BarrierSpecError, match="unsupported"):
        barrier_spec_json(barrier)


def arrival_message(**kwargs):
    return "Someone arrived"


def test_group_barrier_restores_on_arrival_message_callable():
    original = GroupBarrier(
        "pair_hold",
        group_type="pair",
        on_arrival_message=arrival_message,
    )

    restored = barrier_from_spec_json(barrier_spec_json(original))
    spec = json.loads(barrier_spec_json(original))

    assert restored.notify_arrivals is True
    assert restored.on_arrival_message.function is arrival_message
    assert spec["notifications"]["on_arrival_message"]["__type__"] == "callable"
    assert spec["notifications"]["notify_arrivals"] is True
    assert behavior_hash(restored) == behavior_hash(
        GroupBarrier("pair_hold", group_type="pair", notify_arrivals=False)
    )


def test_group_barrier_restores_scalar_presentation_not_waiting_pages():
    original = GroupBarrier(
        "pair_hold",
        group_type="pair",
        content="Waiting for your partner",
        max_wait_time=30,
        max_wait_action="kick",
        notify_arrivals=False,
    )

    restored = barrier_from_spec_json(barrier_spec_json(original))

    assert restored.content == "Waiting for your partner"
    assert restored.max_wait_time == 30
    assert restored.max_wait_action == "kick"
    assert restored.notify_arrivals is False
    assert restored.waiting_logic is None
    assert restored._uses_timeline_hold is True
    assert behavior_hash(restored) == behavior_hash(
        GroupBarrier(
            "pair_hold",
            group_type="pair",
            content="Waiting for someone else",
            max_wait_time=90,
            notify_arrivals=True,
        )
    )


def test_non_json_numeric_state_is_rejected():
    barrier = ThresholdBarrier("threshold", threshold=2)
    barrier.score = float("nan")

    with pytest.raises(BarrierSpecError, match="non-JSON numeric"):
        barrier_spec_json(barrier)
