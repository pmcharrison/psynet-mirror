"""Simulate the complete adaptive procedure outside PsyNet.

Run ``python simulate_procedure.py --help`` for benchmark options. The simulator
compares adaptive predictive-entropy selection with random sampling under both
matching and misspecified synthetic response models.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from adaptive_logic import (
    DEFAULT_BOOTSTRAP_REPLICATES,
    fit_model,
    prior_state,
    select_pair,
)
from response_model import MATCHING, MISSPECIFIED, sample_choices

ROOT = Path(__file__).parent


def load_items(path: Path = ROOT / "stimuli" / "item_bank.csv") -> list[dict]:
    """Load the committed stimulus manifest."""

    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def _all_pairs(item_ids: list[str]) -> list[tuple[str, str, str]]:
    return [
        (f"{item_a}__{item_b}", item_a, item_b)
        for i, item_a in enumerate(item_ids)
        for item_b in item_ids[i + 1 :]
    ]


def _recovery_metrics(estimate: np.ndarray, truth: np.ndarray) -> dict:
    centered_estimate = estimate - estimate.mean()
    centered_truth = truth - truth.mean()
    return {
        "rmse": float(np.sqrt(np.mean(np.square(centered_estimate - centered_truth)))),
        "pearson_r": float(np.corrcoef(centered_estimate, centered_truth)[0, 1]),
    }


def simulate_policy(
    *,
    items: list[dict],
    policy: str,
    scenario: str,
    n_observations: int,
    refit_every: int,
    bootstrap_replicates: int,
    seed: int,
) -> dict:
    """Run one fixed-budget simulated experiment."""

    if policy not in {"adaptive", "random"}:
        raise ValueError("policy must be 'adaptive' or 'random'.")
    parameters = {"matching": MATCHING, "misspecified": MISSPECIFIED}[scenario]
    rng = np.random.default_rng(seed)
    item_ids = [item["item_id"] for item in items]
    truth = np.asarray([float(item["simulation_rank"]) for item in items])
    truth = (truth - truth.mean()) / truth.std()
    truth_by_id = dict(zip(item_ids, truth))
    candidates = _all_pairs(item_ids)
    state = prior_state(item_ids)
    observations: list[tuple[str, str, bool]] = []
    fit_seconds: list[float] = []
    selection_seconds: list[float] = []

    for step in range(n_observations):
        if step and step % refit_every == 0:
            fit = fit_model(
                left_item_ids=np.asarray([row[0] for row in observations]),
                right_item_ids=np.asarray([row[1] for row in observations]),
                chosen_left=np.asarray([row[2] for row in observations]),
                item_ids=item_ids,
                rng=rng,
                bootstrap_replicates=bootstrap_replicates,
            )
            state = fit.state
            fit_seconds.append(fit.diagnostics["fit_seconds"])

        started = time.perf_counter()
        if policy == "adaptive":
            decision = select_pair(
                pair_ids=[row[0] for row in candidates],
                item_a_ids=np.asarray([row[1] for row in candidates]),
                item_b_ids=np.asarray([row[2] for row in candidates]),
                state=state,
                tie_break_seed=seed + step,
            )
            candidate_index = decision["selected_index"]
        else:
            candidate_index = int(rng.integers(0, len(candidates)))
        selection_seconds.append(time.perf_counter() - started)
        _, item_a, item_b = candidates.pop(candidate_index)

        chosen_a = bool(
            sample_choices(
                left_utilities=np.asarray([truth_by_id[item_a]]),
                right_utilities=np.asarray([truth_by_id[item_b]]),
                parameters=parameters,
                rng=rng,
            )[0]
        )
        observations.append((item_a, item_b, chosen_a))

    final_fit = fit_model(
        left_item_ids=np.asarray([row[0] for row in observations]),
        right_item_ids=np.asarray([row[1] for row in observations]),
        chosen_left=np.asarray([row[2] for row in observations]),
        item_ids=item_ids,
        rng=rng,
        bootstrap_replicates=bootstrap_replicates,
    )
    fit_seconds.append(final_fit.diagnostics["fit_seconds"])
    metrics = _recovery_metrics(np.asarray(final_fit.state["utility_mean"]), truth)
    return {
        "policy": policy,
        "scenario": scenario,
        "seed": seed,
        "n_items": len(item_ids),
        "n_observations": n_observations,
        "refit_every": refit_every,
        "bootstrap_replicates": bootstrap_replicates,
        **metrics,
        "mean_fit_seconds": float(np.mean(fit_seconds)),
        "max_fit_seconds": float(np.max(fit_seconds)),
        "mean_selection_seconds": float(np.mean(selection_seconds)),
        "max_selection_seconds": float(np.max(selection_seconds)),
    }


def run_benchmark(
    *,
    n_observations: int,
    refit_every: int,
    bootstrap_replicates: int,
    seed: int,
) -> list[dict]:
    """Compare both policies in matching and misspecified scenarios."""

    items = load_items()
    return [
        simulate_policy(
            items=items,
            policy=policy,
            scenario=scenario,
            n_observations=n_observations,
            refit_every=refit_every,
            bootstrap_replicates=bootstrap_replicates,
            seed=seed,
        )
        for scenario in ["matching", "misspecified"]
        for policy in ["adaptive", "random"]
    ]


def main() -> None:
    """Run the benchmark and print or save JSON results."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--n-observations", type=int, default=400)
    parser.add_argument("--refit-every", type=int, default=50)
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=DEFAULT_BOOTSTRAP_REPLICATES,
    )
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = run_benchmark(
        n_observations=args.n_observations,
        refit_every=args.refit_every,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    output = json.dumps(results, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
