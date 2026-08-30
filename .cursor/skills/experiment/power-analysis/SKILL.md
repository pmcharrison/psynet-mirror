---
name: power-analysis
description: Plan and implement power analyses for PsyNet experiments. Use when choosing participant counts, stimuli, trials, or other design parameters before data collection.
---

# Power analysis

It is good practice to conduct power analyses prior to conducting an experiment. We encourage power analysis as part of the standard experiment implementation workflow.

There are many ways to conduct power analysis. Today's agents are familiar with most standard paradigms and can straightforwardly implement them for a given experiment. This document outlines PsyNet's expectations for how the power analysis code is structured, and provides some general methodological recommendations.

In the absence of overruling instructions, PsyNet recommends a default precision-estimation approach to power analysis.
This is detailed in the `precision-estimation` skill.

Most PsyNet experiments pay participants for the time they spend on the experiment. Some experiments additionally deliver bonuses for good performance. These financial considerations should form part of the power analysis;
see `references/psynet-costing.md` for information.

## Terminology

| Term | Meaning |
| --- | --- |
| Design | Choices under the experimenter's control |
| Assumptions | Values or processes outside the experimenter's control that are assumed for the analysis |
| Scenario | One complete combination of a design and a set of assumptions |
| Replicate | One synthetic experiment generated under a scenario |
| Analysis target | One scientific quantity or question evaluated for each scenario |
| Decision criterion | The rule used to decide whether a design is adequate |

Read [references/terminology.md](references/terminology.md) for fuller definitions and a worked example.

## Response models

Power-analysis methods that simulate participant responses need a simulation
response model. Follow `participant-response-models/SKILL.md` for this.
Record the response-model parameter values or named parameter set in
`audit/power/config.toml`, and record a code hash or version in
`audit/power/run.json`.

## Required files

A power analysis is optional audit evidence. When an experiment has one, it
lives inside the audit packet, and nowhere else:

```text
audit/
└── power/
    ├── config.toml
    ├── core.py
    ├── results.csv
    ├── run.json
    └── analysis.ipynb
```

`psynet audit init` creates `audit/power/` and declares the optional
`power_analysis`, `power_run`, and `power_results` artifacts. `psynet audit
render` then shows the executed notebook and its run provenance in the audit's
"Power analysis" section. Leave those artifacts `missing` when the experiment
does not need a power analysis; they are optional and need no blocker.

All five files are required once a power analysis exists, but contents can be
customized as desired. Additional files are allowed when the method needs them.

A typical data flow is `config.toml` → `core.py` → `results.csv` and `run.json` → `analysis.ipynb` → `audit/PLAN.md`.

### `config.toml`

This should outline key parameters for the power analysis; these will often be lists of parameters such as `n_participants` and `trials_per_participant` that will be explored in a grid search, as well as simulation parameters such as random seed and number of replicates. For example:

```toml
schema_version = "1.0"
method = "precision-estimation"

[decision]
metric = "standardized_margin_of_error"
confidence_level = 0.95
threshold = 0.20

[design]
n_participants = [40, 60, 80, 100]
trials_per_participant = [30, 60]

[assumptions]
trial_noise_sd = [0.8, 1.0, 1.2]

[simulation]
replicates = 1000
base_seed = 20260824
keep_replicates = false
n_jobs = -2
```

### `core.py`

This contains the executable implementation of the chosen method. A suggested
pattern is to read `config.toml`, validate it, evaluate every requested scenario,
and write `results.csv` and `run.json`. A `main()` entry point makes the analysis
easy to run from the experiment root:

```bash
python -m audit.power.core
```

The following pseudocode illustrates the intended orchestration:

```python
def main():
    config = load_toml("audit/power/config.toml")
    rows = []

    for design, assumptions in expand_scenarios(config):
        scenario_id = stable_scenario_id(design, assumptions)
        outcome = run_selected_method(config, design, assumptions)
        for target in outcome.analysis_targets:
            rows.append({
                "result_id": stable_result_id(scenario_id, target.id),
                "scenario_id": scenario_id,
                "analysis_id": target.id,
                "method": config["method"],
                **design,
                **assumptions,
                **target.summary,
            })

    results = DataFrame(rows)
    results.to_csv("audit/power/results.csv", index=False)
    run = {
        "schema_version": "1.0",
        "created_at": utc_now(),
        "method": config["method"],
        "command": "python -m audit.power.core",
        "source_sha256": hash_files("audit/power/config.toml", "audit/power/core.py"),
        "results_sha256": hash_file("audit/power/results.csv"),
        "result_row_count": len(results),
    }
    Path("audit/power/run.json").write_text(json.dumps(run, indent=2))
```

`run_selected_method(...)` and the result summaries are supplied by the chosen
method.

For stochastic methods, reproducibility from the same inputs and random seed is
strongly recommended.

### `results.csv`

This is the tabular output consumed by the notebook and audit. It should be keyed
by the following columns:

- `result_id` - A stable identifier that uniquely identifies the row.
- `scenario_id` - Identifies one combination of a candidate design and a complete
  set of assumptions.
- `analysis_id` - Identifies the analysis target evaluated within that scenario.
- `parameter_id` - Optionally identifies a parameter or component when one
  analysis target produces several result rows. Omit it when each target produces
  exactly one row.

Each `result_id` should be derived from `scenario_id` and `analysis_id`, plus
`parameter_id` when present.

Suggested common columns are:

- `method` - Identifies the power-analysis method.
- `decision_metric` - Names the quantity used to evaluate the design.
- `decision_value` - Gives that metric's value for this row.
- `decision_threshold` - Gives the threshold used to judge adequacy.
- `meets_requirement` - Records whether the row meets the criterion.
- `participant_payment` - Gives the estimated total participant payment for the
  design.
- `currency` - Identifies the currency used for participant payment.

Methods should add their own descriptive and diagnostic columns. Use the same
column names across runs so that notebooks can compare results directly.

### `run.json`

This records provenance for the run that produced `results.csv`. Suggested fields
include the schema version, UTC timestamp, method, invocation, source and result
hashes, Git commit and dirty state, Python and relevant package versions, and
result row count. Include the random seed and replicate count when applicable. A
representative subset is shown in the `core.py` pseudocode above.

### `analysis.ipynb`

This is the executed review document. It should normally read the saved inputs
and outputs rather than rerunning `core.py` or silently altering the results. It
explains the method and assumptions, shows the candidate-design comparison and
participant costs, and states which designs satisfy the decision criterion. Save
the notebook with its review-relevant tables and interactive figures embedded (prefer Plotly unless otherwise specified).

The audit renders this notebook, so its figures must be embedded outputs. Prefer
Plotly and select its notebook MIME renderer before creating figures:

```python
import plotly.io as pio

pio.renderers.default = "plotly_mimetype"
pio.templates.default = "plotly_white"
```

The audit packages Plotly.js with the rendered site, so these figures remain
interactive and work offline. Prefer `plotly_mimetype` over `notebook`,
`notebook_connected`, or HTML-only renderers, which may pull a CDN or embed a
second copy of Plotly. Static SVG or PNG output remains supported.

Power grids invite crowded figures. Follow the layout rules in
`produce-experiment-audit/references/populating-an-audit.md` rather than
inventing a new scheme: keep every simulated condition, facet by row when
panels are needed, give the legend its own space, and verify labels at the
rendered width.

Report precision at single-item (or single-participant) resolution where the
simulation allows it, rather than only at the handful of candidate designs.
A curve over every budget shows where a criterion is first met and how quickly
returns diminish, which a three-point comparison hides. Compute such a curve
with stopping disabled: conditioning on a *realized* length under an adaptive
stopping rule compares self-selected subgroups, because who stops early depends
on the quantity being estimated. Put this fixed-budget curve first. Do not plot
the same curve again at only the candidate budgets.

Treat adaptive stopping as a second-stage optimization. First choose a sensible
fixed budget from the full curve; then report what a stopping rule saves
relative to that baseline and what it costs in precision. Include mean items,
percentage and monetary savings, the fixed-budget metric, the stopping-rule
metric, and their difference. Never describe fewer items as a saving without
showing the corresponding precision change.

For adaptive estimate-recovery analyses, use one primary decision metric and a
standard diagnostic set. Leave `standardized_margin_of_error` as the default
for ordinary precision-estimation power analyses (see the `config.toml` example
above and `precision-estimation/SKILL.md`).

```toml
[metrics]
primary = "rmse"
report = [
    "rmse",
    "pearson_r",
    "mae",
    "bias",
    "mean_posterior_sd",
    "coverage_95",
]
```

Store metric curves in long format (scenario, policy, budget, metric, estimate,
Monte Carlo interval). Average correlations on the Fisher-z scale. Keep the
primary metric permanently visible as its own figure. A companion Plotly figure
may use `updatemenus` buttons for correlation, model SEM (mean posterior SD),
bias, and coverage; keep a table of every metric at the chosen design.
Page-level or ipywidget tabs do not survive the static audit renderer.

Create the companion figure with one trace per displayed scenario/policy and
have each button restyle the traces' `y` and hover values. Do **not** create a
duplicate set of traces for every metric: that inflates the notebook MIME
bundle and can exhaust the bounded audit preview.

Begin the notebook with two short prose sections before any results:

1. **How to read the statistics** defines the primary metric and each
   diagnostic in plain language, says whether higher or lower is better, and
   distinguishes Monte Carlo intervals from participant-level intervals.
2. **Simulation assumptions** states the data-generating model, true-parameter
   distribution, item-bank/calibration assumptions, sample and replicate
   counts, missingness or attrition assumptions, omitted costs, and the purpose
   of each misspecification scenario.

Use `plotly_white` by default. For a dense budget curve, show the primary
metric's Monte Carlo interval as a translucent confidence ribbon rather than
an error bar at every x value; retain the exact bounds in hover text. Error
bars remain appropriate for a sparse set of unrelated candidate designs.

The layout rules and reference code live in
`produce-experiment-audit/references/populating-an-audit.md`. Verify the result
at the rendered width with `psynet audit render` and `psynet audit serve`, in
every metric-button state and after resizing the window, and check for
overlapping labels with the console snippet in that reference. Do not hand over
a figure whose text collides.

After executing it, mark the artifacts present:

```bash
psynet audit mark-present power_analysis
psynet audit mark-present power_run
psynet audit mark-present power_results
```

## Related reading

- If the design is adaptive, treat the selection policy as a design factor
  in this simulation rather than running a separate campaign first. The
  adaptive-experiment skill covers the procedure simulator and the
  policy-comparison checks.
- If the adaptive policy can stop early, do not treat a max-trial cap as the
  realized budget. Either disable the simulation's stopping rule for
  matched-budget cells, or report ``mean_n_observations`` next to RMSE and
  other precision metrics so shorter adaptive runs are not compared as if they
  used the full cap.
