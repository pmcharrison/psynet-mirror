"""Standalone CAT simulator used by power analysis and unit tests."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from adaptive_logic import (
    MAX_ITEMS,
    MIN_ITEMS,
    SE_THRESHOLD,
    fit_participant_posterior,
    select_item,
    should_stop_participant,
)
from response_model.core import ResponseParameters, sample_correct
from stimuli import load_item_bank


@dataclass(frozen=True)
class ProcedureConfig:
    """Settings for one simulated CAT (or random-form) run."""

    policy: str = "max_information"
    min_items: int = MIN_ITEMS
    max_items: int = MAX_ITEMS
    se_threshold: float = SE_THRESHOLD
    stop_early: bool = True
    response_parameters: ResponseParameters = ResponseParameters()


def simulate_one_participant(
    *,
    true_ability: float,
    config: ProcedureConfig,
    rng: np.random.Generator,
    items: tuple[dict, ...] | None = None,
) -> dict:
    """Simulate one participant under ``config.policy``."""
    bank = list(items if items is not None else load_item_bank())
    remaining = list(bank)
    administered = []
    fit = fit_participant_posterior(np.array([]), np.array([]))
    fit_seconds = []
    select_seconds = []

    while remaining:
        n = len(administered)
        if config.stop_early and should_stop_participant(
            n_administered=n,
            posterior_sd=fit.sd,
            min_items=config.min_items,
            max_items=config.max_items,
            se_threshold=config.se_threshold,
        ):
            break
        if n >= config.max_items:
            break

        t0 = time.perf_counter()
        chosen = select_item(
            fit=fit,
            candidate_items=remaining,
            policy=config.policy,
            rng=rng,
        )
        select_seconds.append(time.perf_counter() - t0)

        is_correct = bool(
            sample_correct(
                ability=np.asarray([true_ability]),
                difficulty=np.asarray([chosen["difficulty"]]),
                parameters=config.response_parameters,
                rng=rng,
            )[0]
        )
        administered.append(
            {
                "item_id": chosen["item_id"],
                "difficulty": chosen["difficulty"],
                "correct": int(is_correct),
                "selected_utility": chosen["selected_utility"],
                "predictive_p_correct": chosen["predictive_p_correct"],
                "policy": chosen["policy"],
                "ability_mean": fit.mean,
                "ability_sd": fit.sd,
            }
        )
        remaining = [item for item in remaining if item["item_id"] != chosen["item_id"]]

        t1 = time.perf_counter()
        fit = fit_participant_posterior(
            np.asarray([row["difficulty"] for row in administered]),
            np.asarray([row["correct"] for row in administered]),
        )
        fit_seconds.append(time.perf_counter() - t1)

    return {
        "true_ability": true_ability,
        "ability_mean": fit.mean,
        "ability_sd": fit.sd,
        "n_items": len(administered),
        "trials": administered,
        "mean_fit_seconds": float(np.mean(fit_seconds)) if fit_seconds else 0.0,
        "mean_select_seconds": (
            float(np.mean(select_seconds)) if select_seconds else 0.0
        ),
        "policy": config.policy,
    }


def simulate_many(
    *,
    n_participants: int,
    config: ProcedureConfig,
    rng: np.random.Generator,
    true_ability_sd: float = 1.0,
) -> list[dict]:
    """Draw abilities and simulate independent participants."""
    abilities = rng.normal(0.0, true_ability_sd, size=n_participants)
    return [
        simulate_one_participant(true_ability=float(ability), config=config, rng=rng)
        for ability in abilities
    ]


def checkpoint_estimates(result: dict, checkpoints: list[int]) -> dict[int, dict]:
    """Refit the posterior at each requested test length that was reached."""
    trials = result["trials"]
    out = {}
    for n in checkpoints:
        if n > len(trials):
            continue
        prefix = trials[:n]
        fit = fit_participant_posterior(
            np.asarray([row["difficulty"] for row in prefix]),
            np.asarray([row["correct"] for row in prefix]),
        )
        out[n] = {"ability_mean": fit.mean, "ability_sd": fit.sd}
    return out
