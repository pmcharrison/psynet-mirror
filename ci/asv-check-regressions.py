#!/usr/bin/env python3
"""Fail when selected ASV results regress against a baseline commit."""

from __future__ import annotations

import itertools
import json
import math
import re
from pathlib import Path
from typing import Any

import click

REGRESSION_EXIT_CODE = 2


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


@click.command()
@click.option(
    "--results-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path(".asv/results"),
    show_default=True,
    help="Directory containing ASV result files.",
)
@click.option("--machine", default=None, help="ASV machine name to inspect.")
@click.option("--bench", default=".*", show_default=True, help="Benchmark-name regex.")
@click.option(
    "--factor",
    type=float,
    default=1.25,
    show_default=True,
    help="Regression factor threshold.",
)
@click.argument("base")
@click.argument("head")
@click.pass_context
def main(
    ctx: click.Context,
    results_dir: Path,
    machine: str | None,
    bench: str,
    factor: float,
    base: str,
    head: str,
) -> None:
    """Fail when selected ASV results regress against a baseline commit."""
    bench_regex = re.compile(bench)
    baseline = selected_results(results_dir, machine, base, bench_regex)
    candidate = selected_results(results_dir, machine, head, bench_regex)

    if not candidate:
        raise click.ClickException(f"no candidate ASV results matched {bench!r}")
    if not baseline:
        click.echo(f"No baseline ASV results matched {bench!r}; skipping regression check.")
        return

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
        if is_regression(old, new, factor):
            regressions.append(f"{format_key(key)}: {old!r} -> {new!r}")

    click.echo(
        f"Compared {compared} ASV result(s) matching {bench!r}; "
        f"skipped {skipped} without a comparable baseline."
    )
    if regressions:
        click.echo(f"Detected {len(regressions)} ASV regression(s):", err=True)
        for regression in regressions:
            click.echo(f"- {regression}", err=True)
        ctx.exit(REGRESSION_EXIT_CODE)

    click.echo("No ASV regressions detected.")


if __name__ == "__main__":
    main()
