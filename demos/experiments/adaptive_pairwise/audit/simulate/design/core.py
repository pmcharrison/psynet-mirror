"""Run the fixed-budget adaptive-policy design simulation."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import scipy
import tomllib
from simulate_procedure import load_items, simulate_policy

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = Path(__file__).with_name("config.toml")
RESULTS_PATH = Path(__file__).with_name("results.csv")
RUN_PATH = Path(__file__).with_name("run.json")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _interval(values: list[float]) -> tuple[float, float]:
    mean = float(np.mean(values))
    if len(values) == 1:
        return mean, mean
    half_width = 1.96 * float(np.std(values, ddof=1)) / np.sqrt(len(values))
    return mean - half_width, mean + half_width


def main() -> None:
    """Execute simulations and save aggregate results plus provenance."""

    config = tomllib.loads(CONFIG_PATH.read_text())
    items = load_items()
    started = time.perf_counter()
    replicate_rows = []
    for budget in config["design"]["observation_budgets"]:
        for scenario in config["assumptions"]["scenarios"]:
            for replicate in range(config["simulation"]["replicates"]):
                seed = config["simulation"]["base_seed"] + replicate
                for policy in config["design"]["policies"]:
                    replicate_rows.append(
                        simulate_policy(
                            items=items,
                            policy=policy,
                            scenario=scenario,
                            n_observations=budget,
                            refit_every=config["assumptions"]["refit_every"],
                            bootstrap_replicates=config["assumptions"][
                                "bootstrap_replicates"
                            ],
                            seed=seed,
                        )
                    )

    rows = []
    metrics = [
        "rmse",
        "pearson_r",
        "mean_fit_seconds",
        "mean_selection_seconds",
    ]
    for budget in config["design"]["observation_budgets"]:
        for scenario in config["assumptions"]["scenarios"]:
            matching = [
                row
                for row in replicate_rows
                if row["n_observations"] == budget and row["scenario"] == scenario
            ]
            random_rmse = {
                row["seed"]: row["rmse"]
                for row in matching
                if row["policy"] == "random"
            }
            for policy in config["design"]["policies"]:
                policy_rows = [row for row in matching if row["policy"] == policy]
                for metric in metrics:
                    values = [row[metric] for row in policy_rows]
                    lower, upper = _interval(values)
                    rows.append(
                        {
                            "result_id": f"{scenario}-{policy}-{budget}-{metric}",
                            "scenario_id": scenario,
                            "analysis_id": metric,
                            "policy": policy,
                            "n_observations": budget,
                            "estimate": float(np.mean(values)),
                            "mc95_lower": lower,
                            "mc95_upper": upper,
                            "adaptive_minus_random_rmse": (
                                float(
                                    np.mean(
                                        [
                                            row["rmse"] - random_rmse[row["seed"]]
                                            for row in policy_rows
                                        ]
                                    )
                                )
                                if metric == "rmse" and policy == "adaptive"
                                else ""
                            ),
                            "replicates": len(values),
                        }
                    )

    with RESULTS_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
    )
    RUN_PATH.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "method": config["method"],
                "command": "python -m audit.simulate.design.core",
                "runtime_seconds": time.perf_counter() - started,
                "base_seed": config["simulation"]["base_seed"],
                "replicates": config["simulation"]["replicates"],
                "python_version": platform.python_version(),
                "numpy_version": np.__version__,
                "scipy_version": scipy.__version__,
                "git_sha": git_sha,
                "git_dirty": dirty,
                "config_sha256": _hash(CONFIG_PATH),
                "source_sha256": _hash(Path(__file__)),
                "results_sha256": _hash(RESULTS_PATH),
                "result_row_count": len(rows),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
