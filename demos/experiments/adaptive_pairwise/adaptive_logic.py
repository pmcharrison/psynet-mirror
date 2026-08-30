"""Posterior fitting and pair selection for the adaptive comparison task.

The deployed experiment imports this module without PsyNet or SQLAlchemy
dependencies. Model snapshots therefore use portable dictionaries that can
also be exercised by the standalone simulator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from numpy.random import Generator
from scipy.optimize import minimize
from scipy.special import expit

MODEL_VERSION = "bradley-terry-bootstrap-v1"
OPTIMIZER_VERSION = "predictive-entropy-v1"
DEFAULT_BOOTSTRAP_REPLICATES = 2048


@dataclass(frozen=True)
class FitResult:
    """Portable posterior approximation and fitting diagnostics."""

    state: dict
    diagnostics: dict


def prior_state(item_ids: list[str], prior_sd: float = 2.0) -> dict:
    """Return the zero-data Gaussian prior used by the selection policy."""

    return {
        "item_ids": list(item_ids),
        "utility_mean": [0.0] * len(item_ids),
        "utility_variance": [prior_sd**2] * len(item_ids),
        "model_version": MODEL_VERSION,
    }


def _design_matrix(
    left_item_ids: np.ndarray,
    right_item_ids: np.ndarray,
    item_ids: list[str],
) -> np.ndarray:
    """Encode comparisons while fixing the final item utility to zero."""

    index = {item_id: i for i, item_id in enumerate(item_ids)}
    design = np.zeros((len(left_item_ids), len(item_ids) - 1), dtype=float)
    rows = np.arange(len(left_item_ids))
    left = np.asarray([index[item_id] for item_id in left_item_ids])
    right = np.asarray([index[item_id] for item_id in right_item_ids])
    left_free = left < len(item_ids) - 1
    right_free = right < len(item_ids) - 1
    design[rows[left_free], left[left_free]] += 1.0
    design[rows[right_free], right[right_free]] -= 1.0
    return design


def _fit_map(design: np.ndarray, chosen_left: np.ndarray, prior_sd: float) -> np.ndarray:
    """Fit one regularized Bradley--Terry maximum a posteriori estimate."""

    precision = 1.0 / prior_sd**2

    def objective(free_utilities):
        logits = design @ free_utilities
        negative_log_likelihood = np.logaddexp(0.0, logits).sum() - (
            chosen_left * logits
        ).sum()
        penalty = 0.5 * precision * np.square(free_utilities).sum()
        return negative_log_likelihood + penalty

    def gradient(free_utilities):
        logits = design @ free_utilities
        return design.T @ (expit(logits) - chosen_left) + (
            precision * free_utilities
        )

    result = minimize(
        objective,
        np.zeros(design.shape[1]),
        jac=gradient,
        method="L-BFGS-B",
    )
    if not result.success:
        raise RuntimeError(f"Bradley--Terry fit failed: {result.message}")
    return np.append(result.x, 0.0)


def _laplace_variance(
    design: np.ndarray,
    map_estimate: np.ndarray,
    prior_sd: float,
) -> np.ndarray:
    """Approximate marginal posterior variances around the MAP estimate."""

    probabilities = expit(design @ map_estimate[:-1])
    weights = probabilities * (1.0 - probabilities)
    hessian = design.T @ (weights[:, np.newaxis] * design)
    hessian += np.eye(design.shape[1]) / prior_sd**2
    return np.append(np.diag(np.linalg.inv(hessian)), 0.0)


def fit_model(
    *,
    left_item_ids: np.ndarray,
    right_item_ids: np.ndarray,
    chosen_left: np.ndarray,
    item_ids: list[str],
    rng: Generator,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    prior_sd: float = 2.0,
) -> FitResult:
    """Fit a bootstrap posterior approximation from all observations.

    The repeated refits deliberately represent the expensive part of this
    dogfood experiment. Selection uses only the resulting compact snapshot.
    """

    started = time.perf_counter()
    left_item_ids = np.asarray(left_item_ids)
    right_item_ids = np.asarray(right_item_ids)
    chosen_left = np.asarray(chosen_left, dtype=float)
    if not (
        len(left_item_ids) == len(right_item_ids) == len(chosen_left)
        and len(chosen_left) > 0
    ):
        raise ValueError("Comparison arrays must have the same nonzero length.")
    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be at least 1.")

    design = _design_matrix(left_item_ids, right_item_ids, item_ids)
    map_estimate = _fit_map(design, chosen_left, prior_sd)
    estimates = [map_estimate]
    for _ in range(bootstrap_replicates):
        sample = rng.integers(0, len(chosen_left), size=len(chosen_left))
        estimates.append(_fit_map(design[sample], chosen_left[sample], prior_sd))

    samples = np.asarray(estimates)
    utility_mean = samples.mean(axis=0)
    utility_mean -= utility_mean.mean()
    utility_variance = samples.var(axis=0, ddof=1) + _laplace_variance(
        design,
        map_estimate,
        prior_sd,
    )
    elapsed = time.perf_counter() - started
    return FitResult(
        state={
            "item_ids": list(item_ids),
            "utility_mean": utility_mean.tolist(),
            "utility_variance": utility_variance.tolist(),
            "model_version": MODEL_VERSION,
        },
        diagnostics={
            "fit_seconds": elapsed,
            "bootstrap_replicates": bootstrap_replicates,
            "n_observations": len(chosen_left),
            "optimizer_success": True,
        },
    )


def score_pairs(
    *,
    item_a_ids: np.ndarray,
    item_b_ids: np.ndarray,
    state: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Return information scores and predictive probabilities for pairs."""

    item_ids = state["item_ids"]
    index = {item_id: i for i, item_id in enumerate(item_ids)}
    means = np.asarray(state["utility_mean"])
    variances = np.asarray(state["utility_variance"])
    a = np.asarray([index[item_id] for item_id in item_a_ids])
    b = np.asarray([index[item_id] for item_id in item_b_ids])

    difference_mean = means[a] - means[b]
    difference_variance = variances[a] + variances[b]
    # Logistic-normal approximation to the posterior predictive probability.
    scale = np.sqrt(1.0 + np.pi * difference_variance / 8.0)
    probability_a = expit(difference_mean / scale)
    clipped = np.clip(probability_a, 1e-12, 1.0 - 1e-12)
    entropy = -(clipped * np.log(clipped) + (1.0 - clipped) * np.log(1.0 - clipped))
    information_score = entropy * np.sqrt(difference_variance + 1e-12)
    return information_score, probability_a


def select_pair(
    *,
    pair_ids: list[str],
    item_a_ids: np.ndarray,
    item_b_ids: np.ndarray,
    state: dict,
    tie_break_seed: int,
) -> dict:
    """Select the highest-scoring pair with reproducible random tie-breaking."""

    started = time.perf_counter()
    scores, probabilities = score_pairs(
        item_a_ids=item_a_ids,
        item_b_ids=item_b_ids,
        state=state,
    )
    rng = np.random.default_rng(tie_break_seed)
    tie_breakers = rng.random(len(pair_ids))
    selected_index = int(np.lexsort((tie_breakers, scores))[-1])
    return {
        "selected_index": selected_index,
        "selected_candidate_id": pair_ids[selected_index],
        "selected_utility": float(scores[selected_index]),
        "predictive_probability_item_a": float(probabilities[selected_index]),
        "objective_components": {
            "predictive_entropy_uncertainty_score": float(scores[selected_index]),
            "candidate_count": len(pair_ids),
        },
        "optimizer_version": OPTIMIZER_VERSION,
        "scoring_seconds": time.perf_counter() - started,
    }
