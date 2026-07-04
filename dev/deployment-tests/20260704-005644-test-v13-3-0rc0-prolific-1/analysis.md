# Deployment log analysis: test-v13-3-0rc0-prolific-1 (2026-07-04 00:56 local)

## Deployment metadata

- App name: `test-v13-3-0rc0-prolific-1`
- Experiment URL: <https://test-v13-3-0rc0-prolific-1.experiments1.cococo-lab.cornell.edu/>
- Dashboard URL: <https://test-v13-3-0rc0-prolific-1.experiments1.cococo-lab.cornell.edu/dashboard>
- Deployment branch: `test-deployments/v13.3.0rc0-prolific` (deployed at commit `0835d9647`)
- PsyNet base: tag `v13.3.0rc0` (`59170e2dceab3aba89e99f522eb5dbef7353cd7f`)
- Dallinger: tag `v12.2.1` (`e51709e087d4377c1d073c6cf22dee0e2bb8b765`)
- Prolific study id: `6a488914699fa20ef9203b29`
- Final Prolific study status: `COMPLETED` (12/12 places taken)
- Verdict: **successful deployment and run; no product-breaking errors.**

## Final Prolific submission counts

| Status | Count |
| --- | --- |
| APPROVED | 12 |
| RETURNED | 4 |
| Total submissions | 16 |

One submission passed through `TIMED-OUT` transiently (see worker error below)
before ending as `APPROVED`. Nothing was left `AWAITING REVIEW` or `REJECTED`.

## Dashboard-vs-Prolific reconciliation

16 participant rows for 16 Prolific submissions:

- 11 rows `approved`, `complete=true`, `progress=1.0`: normal completions.
  5 of these received a performance bonus of `0.10`; the rest computed a
  bonus of `0.0` (correctly skipped as below the `0.01` minimum).
- 4 rows `returned` (`id` 5, 8, 11, 14) matching the 4 `RETURNED` Prolific
  submissions. Two of these (5, 14) failed with `UnsuccessfulEndPage` at
  `progress≈0.67` (performance screen-out, then returned as instructed);
  two (8, 11) returned at `progress=0.0` without starting.
- 1 row (`id` 2, assignment `6a48899ee26839a8ff90770f`) is `status=working`,
  `failed=true`, `failed_reason=UnsuccessfulEndPage`, `progress≈0.67`, while
  its Prolific submission ended `APPROVED`. This is the screen-out flow
  (participant compensated via approval) but the PsyNet row was never moved
  to a terminal status. **Minor discrepancy worth watching**: a screened-out
  participant whose submission is approved stays `working` in the dashboard.
- 1 row (`id` 16, assignment `6a488f84923b3c88c8966bdf`) ended `approved`
  after a transient `TIMED-OUT` episode on Prolific (see below).

Base payment `0.45` recorded for all rows; bonuses paid via the Prolific
bulk-bonus API (`bulk-bonus-payments/.../pay/` calls visible in worker log).

## Log findings by container

All raw artifacts live in this deployment's `local/` subfolder (gitignored,
never committed, contains participant identifiers):

- `local/logs.zip` and `local/logs/`: full Dozzle logs, one file per
  container, timestamped `2026-07-04T04-56-45`.
- `local/export/`: database/data export (`psynet export ssh`, non-anonymized)
  with database dump, per-table CSVs, and deployed source code.
- `local/prolific-study-and-submissions.json`: raw Prolific study object and
  all 16 submissions.

- **web** (~1.4 MB): no tracebacks, no 500s, no errors. Launch at
  04:16:09 UTC ("Experiment launch complete!"). Normal request traffic
  afterwards.
- **worker_1** (51 KB): one error cluster at 04:52:01 UTC —
  `approve_participant_submission` for assignment `6a488f84923b3c88c8966bdf`
  (participant 16) raised
  `ProlificServiceException: Prolific session not yet submitted (current status is 'TIMED-OUT')`
  after tenacity retries. The worker logged "Will try to proceed anyway",
  continued, and a later `RecruiterSubmissionComplete` notification for the
  same assignment at 04:54:13 completed the flow; the submission ended
  `APPROVED`. **Non-fatal, known Prolific edge case** (participant submitted
  right around the Prolific timeout boundary).
- **clock** (26 KB): a burst of `Session idle in transaction!` warnings at
  04:24:38 UTC (~5 entries) around `participant_link_barrier` and `process`
  queries, coinciding with several participants hitting a sync barrier
  simultaneously. Idle times ≤ 10.5 s, no deadlocks, no failed jobs.
  **Low-priority noise**, consistent with previous deployments.
- **redis / pgbouncer**: clean; no errors or warnings of interest.

## Timeline of important events (UTC)

- 04:09–04:15 — build on server (first build failed on stale `constraints.txt`
  pinning `dallinger==11.3.1`; fixed by regenerating constraints, commit
  `0835d9647`); second build succeeded.
- 04:14–04:16 — app started, transient TLS errors while Caddy provisioned the
  certificate, `/launch` succeeded on attempt 4, study created on Prolific.
- 04:16:09 — "Experiment launch complete!"; recruitment began immediately.
- 04:19–04:52 — 16 participants recruited; completions, bonuses (5 × `0.10`),
  4 returns, screen-outs at the performance check.
- 04:24:38 — clock `Session idle in transaction!` warning burst (barrier
  contention).
- 04:52:01 — transient approve failure on TIMED-OUT submission
  (participant 16); resolved by 04:54:13.
- ~04:55 — final approval; study `COMPLETED` with 12 approved.
- 04:56:45 — post-completion full Dozzle log download for this analysis.

## Interpretation and severity

1. **Transient TIMED-OUT approval failure (worker)** — expected Prolific edge
   case, self-healed; no action needed. The existing "proceed anyway" handling
   worked as designed.
2. **Screened-out participant left `status=working` (participant 2)** —
   cosmetic/monitoring discrepancy between PsyNet status and Prolific outcome;
   candidate for a small follow-up issue if it recurs.
3. **`Session idle in transaction!` warnings (clock)** — known low-priority
   noise under sync-barrier contention; no deadlocks or failures followed.
4. **Stale tracked `constraints.txt` broke the first build** — fixed on this
   branch; root cause (directory invisible to release tooling) addressed by
   MR !1119, which adds `tests/manual_recruiter_testing` to
   `list_experiment_dirs()` and refreshes the experiment config on `master`.

No confirmed PsyNet/Dallinger bugs. Deployment considered fully successful.
