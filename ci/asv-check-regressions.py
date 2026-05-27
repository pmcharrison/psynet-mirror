#!/usr/bin/env python3
"""Fail when selected ASV results regress against a baseline commit."""

from __future__ import annotations

import argparse
import itertools
import math
import re
import sys
from pathlib import Path
from typing import Any

import json

REGRESSION_EXIT_CODE = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Baseline commit hash or prefix")
    parser.add_argument("head", help="Candidate commit hash or prefix")
    parser.add_argument("--results-dir", default=".asv/results")
    parser.add_argument("--machine", default=None)
    parser.add_argument("--bench", default=".*", help="Benchmark-name regex")
    parser.add_argument("--factor", type=float, default=1.25)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def result_files(results_dir: Path, machine: str | None, commit: str) -> list[Path]:
    commit_prefix = commit[:8]
    machine_dirs = [results_dir / machine] if machine else sorted(results_dir.iterdir())
    paths: list[Path] = []
    for machine_dir in machine_dirs:
        if not machine_dir.is_dir():
            continue
        paths.extend(
            path
            for path in sorted(machine_dir.glob(f"{commit_prefix}*.json"))
            if path.name != "machine.json"
        )
    return paths


def column(entry: list[Any], columns: list[str], name: str, default: Any = None) -> Any:
    try:
        return entry[columns.index(name)]
    except (ValueError, IndexError):
        return default


def selected_results(
    results_dir: Path, machine: str | None, commit: str, bench_regex: re.Pattern[str]
) -> dict[tuple[str, str, tuple[str, ...]], tuple[float | None, str | None]]:
    selected: dict[tuple[str, str, tuple[str, ...]], tuple[float | None, str | None]] = {}
    for path in result_files(results_dir, machine, commit):
        data = load_json(path)
        env_name = data["env_name"]
        columns = data.get("result_columns", ["result", "params", "version"])
        for benchmark_name, entry in data.get("results", {}).items():
            if not bench_regex.search(benchmark_name):
                continue
            values = column(entry, columns, "result")
            params = column(entry, columns, "params", []) or []
            version = column(entry, columns, "version")
            if values is None:
                values = [None]
            if not isinstance(values, list):
                values = [values]
            param_sets = list(itertools.product(*params)) if params else [()]
            for param_set, value in zip(param_sets, values):
                key = (env_name, benchmark_name, tuple(str(p) for p in param_set))
                selected[key] = (value, version)
    return selected


def is_regression(old: float | None, new: float | None, factor: float) -> bool:
    if old is not None and new is None:
        return True
    if old is None or new is None or math.isnan(old) or math.isnan(new):
        return False
    if old == 0:
        return new > 0
    return new > old * factor


def format_key(key: tuple[str, str, tuple[str, ...]]) -> str:
    env_name, benchmark_name, params = key
    params_suffix = f"({', '.join(params)})" if params else ""
    return f"{benchmark_name}{params_suffix} [{env_name}]"


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    bench_regex = re.compile(args.bench)
    baseline = selected_results(results_dir, args.machine, args.base, bench_regex)
    candidate = selected_results(results_dir, args.machine, args.head, bench_regex)

    if not candidate:
        print(f"Error: no candidate ASV results matched {args.bench!r}", file=sys.stderr)
        return 1
    if not baseline:
        print(f"No baseline ASV results matched {args.bench!r}; skipping regression check.")
        return 0

    regressions: list[str] = []
    skipped = 0
    compared = 0
    for key in sorted(candidate):
        if key not in baseline:
            skipped += 1
            continue
        old, old_version = baseline[key]
        new, new_version = candidate[key]
        if old_version != new_version:
            skipped += 1
            continue
        compared += 1
        if is_regression(old, new, args.factor):
            regressions.append(f"{format_key(key)}: {old!r} -> {new!r}")

    print(
        f"Compared {compared} ASV result(s) matching {args.bench!r}; "
        f"skipped {skipped} without a comparable baseline."
    )
    if regressions:
        print(f"Detected {len(regressions)} ASV regression(s):", file=sys.stderr)
        for regression in regressions:
            print(f"- {regression}", file=sys.stderr)
        return REGRESSION_EXIT_CODE

    print("No ASV regressions detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
