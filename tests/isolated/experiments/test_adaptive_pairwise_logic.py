"""Tests for the adaptive pairwise-comparison demo's public model interfaces."""

from pathlib import Path

import numpy as np
import pytest

DEMO = (
    Path(__file__).resolve().parents[3] / "demos" / "experiments" / "adaptive_pairwise"
)


@pytest.fixture()
def model_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(DEMO))
    import adaptive_logic
    import response_model
    import simulate_procedure

    return adaptive_logic, response_model, simulate_procedure


def test_response_model_is_reproducible_and_vectorized(model_modules):
    _, response_model, _ = model_modules
    kwargs = {
        "left_utilities": np.array([1.0, -1.0, 0.0]),
        "right_utilities": np.array([0.0, 0.0, 0.0]),
        "parameters": response_model.MATCHING,
    }

    first = response_model.sample_choices(
        **kwargs,
        rng=np.random.default_rng(42),
    )
    second = response_model.sample_choices(
        **kwargs,
        rng=np.random.default_rng(42),
    )

    assert first.dtype == np.bool_
    assert first.shape == (3,)
    assert np.array_equal(first, second)


def test_fit_and_selection_avoid_an_obvious_pair(model_modules):
    adaptive_logic, _, _ = model_modules
    item_ids = ["a", "b", "c"]
    result = adaptive_logic.fit_model(
        left_item_ids=np.array(["a"] * 30 + ["b"] * 30),
        right_item_ids=np.array(["c"] * 30 + ["c"] * 30),
        chosen_left=np.array([True] * 27 + [False] * 3 + [True] * 3 + [False] * 27),
        item_ids=item_ids,
        rng=np.random.default_rng(7),
        bootstrap_replicates=3,
    )

    decision = adaptive_logic.select_pair(
        pair_ids=["a__b", "a__c", "b__c"],
        item_a_ids=np.array(["a", "a", "b"]),
        item_b_ids=np.array(["b", "c", "c"]),
        state=result.state,
        tie_break_seed=9,
    )

    assert result.state["utility_mean"][0] > result.state["utility_mean"][2]
    assert result.state["utility_mean"][1] < result.state["utility_mean"][2]
    assert decision["selected_candidate_id"] in {"a__c", "b__c"}
    assert decision["scoring_seconds"] < 1.0


def test_prior_selection_is_deterministic(model_modules):
    adaptive_logic, _, _ = model_modules
    state = adaptive_logic.prior_state(["a", "b", "c"])
    kwargs = {
        "pair_ids": ["a__b", "a__c", "b__c"],
        "item_a_ids": np.array(["a", "a", "b"]),
        "item_b_ids": np.array(["b", "c", "c"]),
        "state": state,
        "tie_break_seed": 13,
    }

    first = adaptive_logic.select_pair(**kwargs)
    second = adaptive_logic.select_pair(**kwargs)

    assert first["selected_candidate_id"] == second["selected_candidate_id"]
    assert first["selected_utility"] == second["selected_utility"]


def test_candidate_graph_balances_all_100_items(model_modules):
    adaptive_logic, _, _ = model_modules
    item_ids = [f"item_{index:03d}" for index in range(100)]
    pairs = adaptive_logic.candidate_pairs(item_ids)
    degree = {item_id: 0 for item_id in item_ids}
    for _, item_a, item_b in pairs:
        degree[item_a] += 1
        degree[item_b] += 1

    assert len(pairs) == 500
    assert set(degree.values()) == {10}


def test_standalone_simulation_exercises_the_adaptive_loop(model_modules):
    _, _, simulate_procedure = model_modules
    items = [
        {"item_id": f"item_{index}", "simulation_rank": str(index)}
        for index in range(5)
    ]

    result = simulate_procedure.simulate_policy(
        items=items,
        policy="adaptive",
        scenario="misspecified",
        n_observations=6,
        refit_every=3,
        bootstrap_replicates=1,
        seed=21,
    )

    assert result["n_observations"] == 6
    assert -1.0 <= result["pearson_r"] <= 1.0
    assert result["max_selection_seconds"] < 1.0
