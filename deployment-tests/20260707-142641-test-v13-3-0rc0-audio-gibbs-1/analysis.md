# Deployment Log Analysis: test-v13-3-0rc0-audio-gibbs-1

## Deployment Metadata

- App name: `test-v13-3-0rc0-audio-gibbs-1`
- Experiment: `tests/deployment/audio_gibbs` (audio Gibbs sampler test:
  parselmouth audio synthesis, asset generation/storage, async workers,
  headphone prescreen) — **first deployment of this experiment**
- Experiment URL: `https://test-v13-3-0rc0-audio-gibbs-1.experiments1.cococo-lab.cornell.edu/`
- Dashboard URL: `https://test-v13-3-0rc0-audio-gibbs-1.experiments1.cococo-lab.cornell.edu/dashboard/`
- Deployment branch: `deployment-tests/v13.3.0rc0`
- PsyNet pin: `v13.3.0rc0` (`59170e2dceab3aba89e99f522eb5dbef7353cd7f`)
- Dallinger pin: `v12.2.1` (`e51709e087d4377c1d073c6cf22dee0e2bb8b765`)
- Prolific study id: `6a4d3661687a3b9a8a74c189`
- Final study status: `COMPLETED`
- Deployed in parallel with `test-v13-3-0rc0-prolific-2`.

## Total Cost (Prolific-reported)

`ProlificService.get_total_cost(study_id)` returned **398** minor currency
units (= 3.98 in the account currency), including Prolific fees.

## Final Prolific State

- `status`: `COMPLETED`
- `places_taken`: 6 / `total_available_places`: 6
- `number_of_submissions`: 7
- Submission statuses: 6 `APPROVED`, 1 `RETURNED`

Note: the experiment targets 5 completes (`target_n_participants=5`,
`initial_recruitment_size=3` with auto-recruit top-ups); Prolific ended at 6
approved because a top-up place was filled while the last participants were
in flight — a benign overshoot of one.

## Dashboard-vs-Prolific Reconciliation

7 PsyNet participant rows match the 7 Prolific submissions one-to-one by
assignment id:

- 6 participants `approved`, `complete`, progress 1.0, `base_pay` 0.50 —
  matching the 6 `APPROVED` submissions.
- 1 participant `returned` at progress 0.36 (participant 3, not failed) —
  matching the 1 `RETURNED` submission.

No mismatches.

## Log Findings

Logs reviewed from `local/logs/` (5 containers, downloaded post-completion at
`2026-07-07T18:26:43Z`):

- **Zero error-pattern matches in any container** (no tracebacks, HTTP 500s,
  Prolific API failures, deadlocks, or `Session idle in transaction`
  warnings).
- The worker log shows the audio synthesis / asset generation activity from
  the async jobs (`n_jobs=8` per node) proceeding without failures — the new
  code paths this experiment exists to exercise (parselmouth synthesis, asset
  storage, headphone prescreen) all ran clean under real participants.
- The `/launch` SSL errors in the deploy output were transient
  certificate-provisioning failures; a later launch attempt succeeded.

## Timeline

- 17:12Z deploy started (parallel with the prolific app); image built with the
  extra `praat-parselmouth`/`scipy` dependencies.
- 17:24Z experiment launched; study created and published.
- 17:25–18:10Z recruitment ramped from 3 to 6 places; participants completed
  the headphone prescreen and audio Gibbs trials; one mid-experiment return.
- ~18:15Z study reached `COMPLETED`.
- 18:26Z post-completion logs downloaded; export and raw Prolific JSON
  captured afterwards.

## Interpretation / Verdict

Clean run on the first deployment of this experiment: no errors in any
container, perfect dashboard-vs-Prolific reconciliation, and the
audio-synthesis/asset/async-worker code paths validated end-to-end on
`v13.3.0rc0`.

**Verdict: this run supports promoting `v13.3.0rc0`** (subject to the
parallel `prolific` and Lucid runs).

## Artifacts

- `local/logs.zip`, `local/logs/` — full Dozzle logs (5 containers).
- `local/export/` — `psynet export ssh` output (database, per-table data,
  deployed source code).
- `local/prolific-study-and-submissions.json` — raw Prolific study +
  7 submissions.
