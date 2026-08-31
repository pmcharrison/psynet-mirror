"""Participant-level 1PL CAT: grid posterior, max Fisher information.

This module is PsyNet-free. PsyNet code and ``simulate_procedure.py`` both
import these functions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MODEL_VERSION = "rasch-1pl-grid-v1"
OPTIMIZER_VERSION = "max-fisher-v1"
THETA_GRID = np.linspace(-4.0, 4.0, 161)
PRIOR_SD = 1.0
MIN_ITEMS = 8
MAX_ITEMS = 16
SE_THRESHOLD = 0.40


@dataclass(frozen=True)
class ParticipantFit:
    """Discrete posterior over ability on ``THETA_GRID``."""

    log_posterior: np.ndarray
    mean: float
    sd: float
    n_observations: int

    @property
    def probabilities(self) -> np.ndarray:
        """Normalized posterior masses on the ability grid."""
        weights = np.exp(self.log_posterior - np.max(self.log_posterior))
        return weights / weights.sum()


def logistic(x: np.ndarray) -> np.ndarray:
    """Numerically stable logistic function."""
    z = np.clip(x, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def prior_log_density(theta: np.ndarray, sd: float = PRIOR_SD) -> np.ndarray:
    """Log density of a zero-mean normal prior, up to a constant."""
    return -0.5 * (theta / sd) ** 2


def fit_participant_posterior(
    difficulties: np.ndarray,
    correct: np.ndarray,
    theta_grid: np.ndarray = THETA_GRID,
) -> ParticipantFit:
    """Recompute the 1PL posterior from all observations (from-scratch)."""
    difficulties = np.asarray(difficulties, dtype=float)
    correct = np.asarray(correct, dtype=float)
    log_post = prior_log_density(theta_grid)
    if difficulties.size:
        p = logistic(theta_grid[None, :] - difficulties[:, None])
        y = correct[:, None]
        log_lik = y * np.log(p) + (1.0 - y) * np.log1p(-p)
        log_post = log_post + log_lik.sum(axis=0)
    weights = np.exp(log_post - np.max(log_post))
    probabilities = weights / weights.sum()
    mean = float(np.dot(theta_grid, probabilities))
    second_moment = float(np.dot(theta_grid**2, probabilities))
    sd = float(np.sqrt(max(second_moment - mean**2, 0.0)))
    return ParticipantFit(
        log_posterior=log_post,
        mean=mean,
        sd=sd,
        n_observations=int(difficulties.size),
    )


def fisher_information(theta: np.ndarray, difficulty: np.ndarray) -> np.ndarray:
    """1PL Fisher information I(theta) = p(1-p) for known difficulty."""
    p = logistic(theta - difficulty)
    return p * (1.0 - p)


def expected_information(fit: ParticipantFit, difficulty: float) -> float:
    """Posterior expected Fisher information for a candidate item."""
    info = fisher_information(THETA_GRID, np.asarray(difficulty))
    return float(np.dot(fit.probabilities, info))


def posterior_predictive_p_correct(fit: ParticipantFit, difficulty: float) -> float:
    """Posterior predictive P(correct) used when the item was selected."""
    p = logistic(THETA_GRID - difficulty)
    return float(np.dot(fit.probabilities, p))


def should_stop_participant(
    *,
    n_administered: int,
    posterior_sd: float,
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
    se_threshold: float = SE_THRESHOLD,
) -> bool:
    """Stop after the precision criterion, always respecting min/max length."""
    if n_administered >= max_items:
        return True
    if n_administered < min_items:
        return False
    return posterior_sd <= se_threshold


def select_item(
    *,
    fit: ParticipantFit,
    candidate_items: list[dict],
    policy: str = "max_information",
    rng: np.random.Generator | None = None,
) -> dict:
    """Choose the next item and attach selection diagnostics.

    ``max_information`` is deterministic given the posterior and candidate set.
    ``random`` samples uniformly without using the posterior mean.
    """
    if not candidate_items:
        raise ValueError("No candidate items remain.")
    if policy == "random":
        if rng is None:
            raise ValueError("Random selection requires an RNG.")
        chosen = dict(candidate_items[int(rng.integers(len(candidate_items)))])
        utility = expected_information(fit, chosen["difficulty"])
    elif policy == "max_information":
        scored = [
            (expected_information(fit, item["difficulty"]), item["item_id"], item)
            for item in candidate_items
        ]
        scored.sort(key=lambda row: (-row[0], row[1]))
        utility, _, chosen_item = scored[0]
        chosen = dict(chosen_item)
    else:
        raise ValueError(f"Unknown policy: {policy}")

    chosen["selected_utility"] = float(utility)
    chosen["predictive_p_correct"] = posterior_predictive_p_correct(
        fit, chosen["difficulty"]
    )
    chosen["candidate_count"] = len(candidate_items)
    chosen["policy"] = policy
    chosen["optimizer_version"] = OPTIMIZER_VERSION
    chosen["model_version"] = MODEL_VERSION
    return chosen
