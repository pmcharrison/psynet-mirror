---
name: implement-experiment
description: Coordinate the end-to-end implementation of a PsyNet experiment from a natural-language specification.
---

# Implement a PsyNet experiment

Use this skill to coordinate the implementation workflow. Follow the specialist
skill named at each stage for its implementation details.

## Set up the experiment

Use `explore-psynet-repository/SKILL.md` to inspect the closest PsyNet demos and
framework APIs. Start from the closest authored demo or an empty experiment
directory, then run `psynet setup`; do not hand-write PsyNet boilerplate.

Initialize the audit before planning and meaningful implementation runs:

```bash
psynet audit init
```

Follow `produce-experiment-audit/SKILL.md` for audit paths and bookkeeping.

## Agree the plan

Write the plan in `audit/PLAN.md`. Describe what participants experience, how
they are assigned, and what the experiment records. Explain the planned PsyNet
structure and the analysis that will answer the research questions. Include
hypotheses when the specification calls for them. State the assumptions of the
scientific participant-response model.

For a nontrivial participant task, the plan should normally include a brief
training or practice phase before scored trials. Describe what participants
practise and how they proceed to the main task, or explain why practice is not
needed.

Leave the scale of the design provisional in the first draft. Ask the user to
review that draft before running the power analysis.

Every experiment must define its scientific participant-response model in the
top-level `response_model/` package described by
`participant-response-models/SKILL.md`. Implement it after the initial plan
review and before power analysis. Import the same package from the power
analysis and the experiment's scientific bot responses.

When accumulated responses influence later measurements or assignments, follow
`make-experiment-adaptive/SKILL.md`. Use its standalone simulation to benchmark
the adaptive policy against a credible non-adaptive alternative, including
robustness to plausible model misspecification. Review this benchmark before
using power analysis to select the final design.

Follow `power-analysis/SKILL.md`, show the results to the user, and revise the
plan together with the selected design and its assumptions. Begin implementation
once the revised plan is agreed.

## Implement

Use `develop-experiment-back-end/SKILL.md` for the timeline and trial
architecture, and `develop-experiment-front-end/SKILL.md` for participant-facing
pages and controls.

Keep `audit/PLAN.md` current when implementation decisions alter the agreed
design.

## Test

Follow `test-experiment/SKILL.md` and complete all five checks it requires.

## Analyze and report

Run the planned analysis against the simulated export. Save the executed review
notebook as `audit/analyses/analysis.ipynb`, including the tables and figures
needed to inspect the results. Follow the analysis conventions in
`produce-experiment-audit/references/populating-an-audit.md`.

Summarize the completed work and remaining limitations in `audit/REPORT.md`.

## Hand off

Close and render the audit using `produce-experiment-audit/SKILL.md`. Offer to
open the rendered audit for the user. Use `prepare-experiment-tunnel/SKILL.md`
only when a temporary public preview is requested.
