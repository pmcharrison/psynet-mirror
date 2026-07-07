# Deployment Log Analysis: test-v13-3-0rc0-prolific-2

## Deployment Metadata

- App name: `test-v13-3-0rc0-prolific-2`
- Experiment: `tests/deployment/prolific` (basic Prolific manual recruiter test)
- Experiment URL: `https://test-v13-3-0rc0-prolific-2.experiments1.cococo-lab.cornell.edu/`
- Dashboard URL: `https://test-v13-3-0rc0-prolific-2.experiments1.cococo-lab.cornell.edu/dashboard/`
- Deployment branch: `deployment-tests/v13.3.0rc0`
- PsyNet pin: `v13.3.0rc0` (`59170e2dceab3aba89e99f522eb5dbef7353cd7f`)
- Dallinger pin: `v12.2.1` (`e51709e087d4377c1d073c6cf22dee0e2bb8b765`)
- Prolific study id: `6a4d362500833d18d8606667`
- Study published: `2026-07-07T17:23:53Z`; final study status: `COMPLETED`
- Deployed in parallel with `test-v13-3-0rc0-audio-gibbs-1` (first dual-app
  deployment test per the updated deployment-test skill).

## Total Cost (Prolific-reported)

`ProlificService.get_total_cost(study_id)` returned **1074** minor currency
units (= 10.74 in the account currency, GBP-configured study), including
Prolific fees.

## Final Prolific State

- `status`: `COMPLETED`
- `places_taken`: 12 / `total_available_places`: 12
- `number_of_submissions`: 21
- Submission statuses: 12 `APPROVED`, 6 `RETURNED`, 3 `TIMED-OUT`

## Dashboard-vs-Prolific Reconciliation

The PsyNet participant table has 19 rows; Prolific shows 21 submissions, so 2
submissions never reached the PsyNet ad/consent flow (returned or timed out
before entering) — expected Prolific behavior.

- 12 participants `approved`, `complete`, progress 1.0, `base_pay` 0.50 (5 of
  them additionally received a 0.10 performance bonus) — these match the 12
  `APPROVED` submissions one-to-one by assignment id.
- 4 participants `returned` + failed with `failed_reason=UnsuccessfulEndPage`
  at progress ~0.67 (participants 2, 8, 14, 17); three received compensation
  bonuses of 0.35–0.37. These are the experiment's intended screening path
  (failing the performance check ends the experiment unsuccessfully) and map
  to `RETURNED` submissions.
- 3 participants `abandoned` at progress ~0.67 (participants 5, 7, 11; 5 and
  11 failed with `UnsuccessfulEndPage`, 7 not failed) — these map to the
  `TIMED-OUT`/`RETURNED` remainder.
- No dashboard-vs-Prolific status contradictions were found (unlike the
  earlier `fh-test-deployment-1` run, which had an approved-vs-TIMED-OUT
  mismatch).

## Log Findings

Logs reviewed from `local/logs/` (5 containers, downloaded post-completion at
`2026-07-07T18:26:41Z`):

- `worker`: one non-fatal `ProlificServiceException: Prolific session not yet
  submitted (current status is 'ACTIVE')` traceback at 17:31:23 during
  `approve_participant_submission` for assignment `6a4d36aea2dd92d7cd18907c`
  (participant 6), logged as "Will try to proceed anyway". The participant
  was later approved successfully (dashboard row `approved`/`complete`, the
  submission is `APPROVED` on Prolific), so this is the known benign
  approve-before-submit race documented in the skill.
- `web`: no HTTP 500s, no tracebacks. The `/launch` SSL errors visible in the
  deploy output were transient certificate-provisioning failures; a later
  launch attempt succeeded.
- `clock`, `redis`, `pgbouncer`: clean; zero `Session idle in transaction`
  warnings this run.
- No deadlocks, `UndefinedTable`, or worker/clock restarts.

## Timeline

- 17:12Z deploy started (parallel with the audio-gibbs app); Docker image
  built and pushed.
- 17:23Z experiment launched (after transient SSL retries); study created
  and published.
- 17:24–18:05Z recruitment ramped from 3 toward 12 places via auto-recruit
  top-ups; completions, returns, and time-outs accumulated.
- ~18:20Z study reached `COMPLETED` (12/12 places taken).
- 18:26Z post-completion logs downloaded; export and raw Prolific JSON
  captured afterwards.

## Interpretation / Verdict

No bugs found. The single worker traceback is the known non-fatal
approval-retry race and resolved itself. Screening failures and abandonments
followed the experiment's intended paths, payments (base + bonuses,
including compensation bonuses for screened-out participants) look
consistent, and recruitment topped up automatically to target.

**Verdict: this run supports promoting `v13.3.0rc0`** (subject to the
parallel `audio_gibbs` and Lucid runs).

## Artifacts

- `local/logs.zip`, `local/logs/` — full Dozzle logs (5 containers).
- `local/export/` — `psynet export ssh` output (database, per-table data,
  deployed source code).
- `local/prolific-study-and-submissions.json` — raw Prolific study +
  21 submissions.
