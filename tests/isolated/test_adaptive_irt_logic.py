"""Unit tests for the adaptive IRT demo's PsyNet-free CAT logic."""

import sys
from pathlib import Path

import numpy as np
import pytest

DEMO = Path(__file__).resolve().parents[2] / "demos" / "experiments" / "adaptive_irt"
sys.path.insert(0, str(DEMO))

from adaptive_logic import (  # noqa: E402
    THETA_GRID,
    expected_information,
    fit_participant_posterior,
    select_item,
    should_stop_participant,
)
from response_model.core import ResponseParameters, sample_correct  # noqa: E402
from simulate_procedure import ProcedureConfig, simulate_one_participant  # noqa: E402
from stimuli import load_item_bank  # noqa: E402


def test_item_bank_is_well_formed():
    items = load_item_bank()
    assert len(items) >= 16
    ids = [item["item_id"] for item in items]
    assert len(ids) == len(set(ids))
    for item in items:
        assert item["correct_choice"] in item["choices"]
        assert len(item["choices"]) == 4


def test_sample_correct_is_reproducible():
    parameters = ResponseParameters()
    kwargs = dict(
        ability=np.asarray([0.0, 1.0, -1.0]),
        difficulty=np.asarray([0.0, 0.0, 0.0]),
        parameters=parameters,
    )
    first = sample_correct(**kwargs, rng=np.random.default_rng(7))
    second = sample_correct(**kwargs, rng=np.random.default_rng(7))
    assert np.array_equal(first, second)
    assert first.shape == (3,)


def test_max_information_selects_nearest_unused_item():
    fit = fit_participant_posterior(np.array([]), np.array([]))
    items = [
        {"item_id": "hard", "difficulty": 2.0},
        {"item_id": "easy", "difficulty": -2.0},
        {"item_id": "mid", "difficulty": 0.0},
    ]
    chosen = select_item(fit=fit, candidate_items=items, policy="max_information")
    assert chosen["item_id"] == "mid"
    assert chosen["selected_utility"] == pytest.approx(
        expected_information(fit, 0.0), rel=1e-9
    )


def test_max_information_is_deterministic():
    fit = fit_participant_posterior(np.array([0.0, 0.5]), np.array([1.0, 0.0]))
    items = list(load_item_bank())
    first = select_item(fit=fit, candidate_items=items, policy="max_information")
    second = select_item(fit=fit, candidate_items=items, policy="max_information")
    assert first["item_id"] == second["item_id"]


def test_stopping_rule_respects_min_and_max():
    assert not should_stop_participant(n_administered=4, posterior_sd=0.1)
    assert should_stop_participant(n_administered=8, posterior_sd=0.2)
    assert not should_stop_participant(n_administered=8, posterior_sd=0.8)
    assert should_stop_participant(n_administered=16, posterior_sd=1.5)


def test_empty_posterior_is_the_prior():
    fit = fit_participant_posterior(np.array([]), np.array([]))
    assert fit.n_observations == 0
    assert fit.mean == pytest.approx(0.0, abs=1e-8)
    assert fit.sd == pytest.approx(1.0, abs=0.05)
    assert THETA_GRID.shape == fit.log_posterior.shape


def test_simulate_procedure_records_unique_items():
    rng = np.random.default_rng(0)
    result = simulate_one_participant(
        true_ability=0.0,
        config=ProcedureConfig(policy="max_information", stop_early=True),
        rng=rng,
    )
    item_ids = [trial["item_id"] for trial in result["trials"]]
    assert 8 <= result["n_items"] <= 16
    assert len(item_ids) == len(set(item_ids))
    assert result["mean_select_seconds"] < 1.0
    assert result["mean_fit_seconds"] < 1.0
