"""Monte Carlo precision estimation for the adaptive arithmetic CAT."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tomllib

EXPERIMENT_ROOT = Path(__file__).resolve().parents[3]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from response_model.core import ResponseParameters  # noqa: E402
from simulate_procedure import ProcedureConfig, simulate_one_participant  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("config.toml")
RESULTS_PATH = Path(__file__).with_name("results.csv")
RUN_PATH = Path(__file__).with_name("run.json")


def _load_config() -> dict:
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.std() < 1e-12 or y.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _metrics(truth: np.ndarray, estimate: np.ndarray, sd: np.ndarray) -> dict:
    error = estimate - truth
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))
    coverage = float(np.mean(np.abs(error) <= 1.96 * sd))
    return {
        "rmse": rmse,
        "mae": mae,
        "bias": bias,
        "pearson_r": _pearson(truth, estimate),
        "mean_posterior_sd": float(np.mean(sd)),
        "coverage_95": coverage,
        "mean_n_observations": float(len(truth)),
    }


def _simulate_replicate(
    *,
    n_participants: int,
    config: ProcedureConfig,
    true_ability_sd: float,
    rng: np.random.Generator,
) -> dict:
    abilities = rng.normal(0.0, true_ability_sd, size=n_participants)
    results = [
        simulate_one_participant(
            true_ability=float(ability),
            config=config,
            rng=rng,
        )
        for ability in abilities
    ]
    truth = np.asarray([row["true_ability"] for row in results])
    estimate = np.asarray([row["ability_mean"] for row in results])
    sd = np.asarray([row["ability_sd"] for row in results])
    n_items = np.asarray([row["n_items"] for row in results], dtype=float)
    summary = _metrics(truth, estimate, sd)
    summary["mean_n_observations"] = float(np.mean(n_items))
    summary["mean_fit_seconds"] = float(
        np.mean([row["mean_fit_seconds"] for row in results])
    )
    summary["mean_select_seconds"] = float(
        np.mean([row["mean_select_seconds"] for row in results])
    )
    return summary


def _scenario_id(policy: str, max_items: int, guessing: float, stop_early: bool) -> str:
    stopping = "stop" if stop_early else "fixed"
    return f"{policy}_m{max_items}_g{guessing:.2f}_{stopping}"


def main() -> None:
    config = _load_config()
    replicates = int(config["simulation"]["replicates"])
    base_seed = int(config["simulation"]["base_seed"])
    n_participants = int(config["design"]["n_participants"][0])
    true_ability_sd = float(config["assumptions"]["true_ability_sd"][0])
    wage = float(config["cost"]["wage_per_hour"])
    fixed_seconds = float(config["cost"]["fixed_seconds"])
    seconds_per_item = float(config["cost"]["seconds_per_item"])
    threshold = float(config["decision"]["threshold"])
    rows = []

    cells = []
    for policy in config["design"]["policies"]:
        for max_items in config["design"]["max_items"]:
            for guessing in config["assumptions"]["guessing"]:
                cells.append(
                    {
                        "policy": policy,
                        "max_items": int(max_items),
                        "guessing": float(guessing),
                        "stop_early": False,
                        "min_items": int(max_items),
                        "se_threshold": 0.0,
                    }
                )
    for policy in config["design"]["policies"]:
        for guessing in config["assumptions"]["guessing"]:
            cells.append(
                {
                    "policy": policy,
                    "max_items": int(config["stopping"]["max_items"]),
                    "guessing": float(guessing),
                    "stop_early": True,
                    "min_items": int(config["stopping"]["min_items"]),
                    "se_threshold": float(config["stopping"]["se_threshold"]),
                }
            )

    for cell in cells:
        replicate_metrics = []
        for replicate in range(replicates):
            cell_key = json.dumps(cell, sort_keys=True).encode()
            cell_seed = int(hashlib.md5(cell_key).hexdigest()[:8], 16)
            rng = np.random.default_rng(base_seed + replicate * 1009 + cell_seed)
            procedure = ProcedureConfig(
                policy=cell["policy"],
                min_items=cell["min_items"],
                max_items=cell["max_items"],
                se_threshold=cell["se_threshold"],
                stop_early=cell["stop_early"],
                response_parameters=ResponseParameters(guessing=cell["guessing"]),
            )
            replicate_metrics.append(
                _simulate_replicate(
                    n_participants=n_participants,
                    config=procedure,
                    true_ability_sd=true_ability_sd,
                    rng=rng,
                )
            )
        metric_names = list(replicate_metrics[0].keys())
        scenario = _scenario_id(
            cell["policy"], cell["max_items"], cell["guessing"], cell["stop_early"]
        )
        mean_n = float(
            np.mean([row["mean_n_observations"] for row in replicate_metrics])
        )
        payment = (
            n_participants * wage * (fixed_seconds + mean_n * seconds_per_item) / 3600
        )
        for metric in metric_names:
            values = np.asarray([row[metric] for row in replicate_metrics], dtype=float)
            estimate = float(np.nanmean(values))
            se = float(np.nanstd(values, ddof=1) / np.sqrt(len(values)))
            decision_value = estimate if metric == "rmse" else float("nan")
            rows.append(
                {
                    "result_id": f"{scenario}__{metric}",
                    "scenario_id": scenario,
                    "analysis_id": "ability",
                    "parameter_id": metric,
                    "method": config["method"],
                    "policy": cell["policy"],
                    "max_items": cell["max_items"],
                    "stop_early": cell["stop_early"],
                    "guessing": cell["guessing"],
                    "n_participants": n_participants,
                    "metric": metric,
                    "estimate": estimate,
                    "mc_se": se,
                    "decision_metric": config["decision"]["metric"],
                    "decision_value": decision_value,
                    "decision_threshold": threshold,
                    "meets_requirement": (
                        bool(estimate <= threshold) if metric == "rmse" else False
                    ),
                    "participant_payment": payment,
                    "currency": config["cost"]["currency"],
                }
            )

    results = pd.DataFrame(rows)
    results.to_csv(RESULTS_PATH, index=False)
    source_files = [
        CONFIG_PATH,
        Path(__file__),
        EXPERIMENT_ROOT / "adaptive_logic.py",
        EXPERIMENT_ROOT / "simulate_procedure.py",
        EXPERIMENT_ROOT / "response_model" / "core.py",
    ]
    run = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": config["method"],
        "command": "python audit/simulate/design/core.py",
        "source_sha256": {
            str(path.relative_to(EXPERIMENT_ROOT)): _sha256(path)
            for path in source_files
        },
        "results_sha256": _sha256(RESULTS_PATH),
        "result_row_count": int(len(results)),
        "replicates": replicates,
        "base_seed": base_seed,
        "response_model": "response_model.core.ResponseParameters",
    }
    RUN_PATH.write_text(json.dumps(run, indent=2))
    print(f"Wrote {RESULTS_PATH} ({len(results)} rows)")


if __name__ == "__main__":
    main()
