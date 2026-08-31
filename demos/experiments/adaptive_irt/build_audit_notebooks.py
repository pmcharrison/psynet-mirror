"""Build and execute audit notebooks."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parent
ANALYSIS = ROOT / "audit/simulate/analysis/analysis.ipynb"
DESIGN = ROOT / "audit/simulate/design/simulation.ipynb"


def _code(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(source)


def _md(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(source)


def write_analysis() -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        _md("# Simulated export analysis"),
        _md(
            "This notebook reads the PsyNet bot export for the adaptive arithmetic CAT. "
            "The answers are simulated, not human."
        ),
        _code(
            """
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

%config InlineBackend.figure_formats = ["svg"]

here = Path.cwd()
root = here if (here / "experiment.py").exists() else here.parents[2]
export = root / "audit/simulate/analysis/simulated_export/regular/basic_data"
trials = pd.read_csv(export / "trial.csv")
participants = pd.read_csv(export / "participant.csv")
decisions = pd.read_csv(export / "adaptive_decision.csv")
print(root)
print("trials", len(trials), "participants", len(participants), "decisions", len(decisions))
trials.head()
"""
        ),
        _md("## Participants"),
        _code("participants"),
        _md("## Adaptive decisions"),
        _code(
            """
adaptive = trials[trials.phase == "adaptive"].copy()
print("unique items per participant")
print(adaptive.groupby("participant_id").item_id.nunique())
print("decision rows match adaptive trials:", len(decisions) == len(adaptive))
decisions.head()
"""
        ),
        _md("## Item difficulty over the CAT"),
        _code(
            """
adaptive = adaptive.sort_values(["participant_id", "id"])
adaptive["cat_index"] = adaptive.groupby("participant_id").cumcount() + 1
fig, ax = plt.subplots(figsize=(7, 4))
for pid, group in adaptive.groupby("participant_id"):
    profile = participants.loc[participants.id == pid, "response_profile"].iloc[0]
    ability = participants.loc[participants.id == pid, "true_ability"].iloc[0]
    ax.plot(group.cat_index, group.difficulty, marker="o", label=f"p{pid} {profile} θ={ability}")
ax.set_xlabel("Scored item number")
ax.set_ylabel("Item difficulty")
ax.legend()
ax.set_title("Selected item difficulty across the CAT")
plt.show()
"""
        ),
        _md("## Recovered vs stored ability"),
        _code(
            """
fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(participants.true_ability, participants.ability_mean)
for _, row in participants.iterrows():
    ax.errorbar(row.true_ability, row.ability_mean, yerr=row.ability_sd, fmt="o")
    ax.annotate(row.response_profile, (row.true_ability, row.ability_mean))
lims = [-2, 2]
ax.plot(lims, lims, color="gray", linestyle="--")
ax.set_xlabel("Stored true ability (simulation)")
ax.set_ylabel("Posterior mean")
ax.set_title("Three bot profiles, not a human sample")
plt.show()
"""
        ),
    ]
    ANALYSIS.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, ANALYSIS)


def write_design() -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        _md("# Design simulation"),
        _md(
            """## How to read the statistics

The primary metric is **RMSE**: the root mean squared error of the posterior mean of ability versus the simulated true ability. Lower is better. The decision threshold was 0.45. Monte Carlo intervals are the standard error of that RMSE across 20 simulated experiments, not participant-level confidence intervals.

Other diagnostics: Pearson *r* (higher better), MAE, bias (near 0 better), mean posterior SD, and 95% interval coverage (near 0.95 better).
"""
        ),
        _md(
            """## Simulation assumptions

Responses are generated from a 1PL model, or a 3PL with guessing 0.25. True abilities are Normal(0, 1). The item bank is the same 32-item judgement-calibrated set used in the demo. Each replicate has 40 participants. Stopping is disabled on the matched-budget grid. A separate stopping-enabled cell uses min 8 / max 16 / SE 0.40. Costs use $12/hour, 35 s fixed and 8 s per scored item. Attrition, recruiter fees, and bonuses are omitted.
"""
        ),
        _code(
            """
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.renderers.default = "plotly_mimetype"
pio.templates.default = "plotly_white"

here = Path.cwd()
root = here if (here / "experiment.py").exists() else here.parents[2]
results = pd.read_csv(root / "audit/simulate/design/results.csv")
results.head()
"""
        ),
        _md("## Power analysis"),
        _code(
            """
rmse = results[(results.metric == "rmse") & (~results.stop_early)].copy()
rmse["scenario"] = rmse.apply(
    lambda r: ("Matching 1PL" if r.guessing == 0 else "3PL guessing")
    + ", "
    + ("Max information" if r.policy == "max_information" else "Random"),
    axis=1,
)
fig = go.Figure()
for name, group in rmse.groupby("scenario"):
    group = group.sort_values("max_items")
    fig.add_trace(
        go.Scatter(
            x=group.max_items,
            y=group.estimate,
            error_y=dict(type="data", array=group.mc_se, visible=True),
            mode="lines+markers",
            name=name,
        )
    )
fig.add_hline(y=0.45, line_dash="dash", annotation_text="RMSE threshold 0.45")
fig.update_layout(
    height=420,
    margin=dict(l=70, r=30, t=90, b=60),
    title=dict(text="Ability RMSE at matched test length", x=0, xanchor="left"),
    xaxis_title="Scored items",
    yaxis_title="RMSE",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
    xaxis=dict(tickvals=[8, 12, 16]),
)
fig
"""
        ),
        _md("## Adaptive procedure"),
        _code(
            """
stop = results[(results.metric == "rmse")].copy()
table = stop.pivot_table(
    index=["policy", "guessing", "stop_early", "max_items"],
    values=["estimate", "mc_se", "meets_requirement", "participant_payment"],
    aggfunc="first",
).reset_index()
table
"""
        ),
        _md(
            """## Decision

No candidate design met RMSE ≤ 0.45. At 16 well-specified items, max-information RMSE was about 0.48 versus 0.53 for random order: a modest gain, not enough for the pre-set criterion. The SE-0.40 stopping rule never shortened the test in these simulations (mean length 16). The 3PL-guessing scenario is substantially worse for both policies.

The demo still uses max-information CAT because the goal is to exercise the adaptive workflow, not to claim a powered arithmetic study. For a real study, enlarge or empirically calibrate the item bank, or relax the precision target.
"""
        ),
    ]
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, DESIGN)


def execute(path: Path) -> None:
    with path.open() as handle:
        nb = nbf.read(handle, as_version=4)
    preprocessor = ExecutePreprocessor(timeout=180, kernel_name="python3")
    preprocessor.preprocess(nb, {"metadata": {"path": str(ROOT)}})
    nbf.write(nb, path)
    print("executed", path)


if __name__ == "__main__":
    write_analysis()
    write_design()
    execute(ANALYSIS)
    execute(DESIGN)
