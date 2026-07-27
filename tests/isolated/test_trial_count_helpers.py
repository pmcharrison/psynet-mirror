"""Tests for explicit trial/network count helpers."""

from psynet.trial.chain import (
    count_completed_trials_for_network,
    count_participant_trials_in_block,
    count_participant_trials_in_trial_maker,
    count_viable_trials_for_node,
    count_viable_trials_for_nodes,
)


def test_count_viable_trials_for_nodes_empty():
    assert count_viable_trials_for_nodes([]) == {}
    assert count_viable_trials_for_nodes([None]) == {}


def test_count_helpers_are_importable():
    # Smoke-check the public helper API used by chain allocation.
    assert callable(count_viable_trials_for_node)
    assert callable(count_completed_trials_for_network)
    assert callable(count_participant_trials_in_trial_maker)
    assert callable(count_participant_trials_in_block)
