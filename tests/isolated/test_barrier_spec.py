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

    assert json.loads(serialized) == {
        "class": "test_barrier_spec.ThresholdBarrier",
        "state": {"id": "threshold", "threshold": 2},
        "version": 1,
    }
    assert isinstance(restored, ThresholdBarrier)
    assert restored.id == "threshold"
    assert restored.threshold == 2


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
