# Deployment Log Analysis: fh-test-deployment-1

## Deployment Metadata

- App name: `fh-test-deployment-1`
- Experiment URL: `https://fh-test-deployment-1.experiments1.cococo-lab.cornell.edu/`
- Dashboard URL: `https://fh-test-deployment-1.experiments1.cococo-lab.cornell.edu/dashboard/`
- Prolific study id: `6a3e7fbaa0e9a130356fbc4e`
- Final Prolific study status: `COMPLETED`
- PsyNet deployment dependency commit: `e27ff238beccab96fe747c08ed563bd66b1c55ec`
- Dallinger commit: `fa8f0d23640f29072dbe9455c56821542127be0c`
- Analysis timestamp: `2026-06-26 10:03:26` local time
- Downloaded logs ZIP: `dev/deployment-log-analyses/20260626-100326-fh-test-deployment-1-logs.zip`
- Source extracted logs: `dev/tmp/dozzle-fh-test-deployment-1-study-completed/extracted/`

Log files reviewed:

- `fh-test-deployment-1-web-1-2026-06-26T13-57-31.log`
- `fh-test-deployment-1-worker_1-1-2026-06-26T13-57-31.log`
- `fh-test-deployment-1-clock-1-2026-06-26T13-57-31.log`
- `fh-test-deployment-1-redis-1-2026-06-26T13-57-31.log`
- `fh-test-deployment-1_pgbouncer-2026-06-26T13-57-31.log`

## Executive Summary

The deployment launched successfully, recruited to completion on Prolific, and reached Prolific study status `COMPLETED`. The final direct Prolific count was 22 submissions: 12 `APPROVED`, 9 `RETURNED`, and 1 `TIMED-OUT`.

The most important issue is a dashboard-vs-Prolific inconsistency: PsyNet participant `4` is marked `approved`/complete in the dashboard, but the corresponding Prolific submission `6a3e8191a6fbc404640781d9` ended as `TIMED-OUT`. The worker log contains the related `ProlificServiceException` traceback while trying to approve that timed-out submission. This looks like the main item to investigate.

No HTTP 500s, deadlocks, undefined-table errors, or deployment-stopping crashes were found in the final logs. There are repeated `Session idle in transaction!` warnings in pgbouncer and non-fatal Prolific approval tracebacks in the worker log.

## Final Prolific State

Final study fields:

- `status`: `COMPLETED`
- `places_taken`: `12`
- `total_available_places`: `12`
- `number_of_submissions`: `22`
- `published_at`: `2026-06-26T13:39:01.429000Z`

Final submission status counts:

- `APPROVED`: 12
- `RETURNED`: 9
- `TIMED-OUT`: 1
- `ACTIVE`: 0

## Dashboard Summary

The PsyNet dashboard participant table contained 18 participant rows:

- `approved`: 12
- `returned`: 6
- `complete=True`: 12
- `complete=False`: 6
- `failed=True`: 6
- `failed=False`: 12

The six failed dashboard rows all had `failed_reason = UnsuccessfulEndPage` and `failure_tags` containing `UnsuccessfulEndPage`. Some returned participants also had `assignment_return_result` entries in `branch_log`, indicating the return-for-bonus path ran.

## Dashboard vs Prolific Reconciliation

### Counts

The high-level counts do not line up one-to-one:

- Prolific has 22 submissions.
- PsyNet has 18 participant rows.
- Prolific has 9 `RETURNED` submissions; PsyNet has 6 returned participant rows.
- Prolific has 1 `TIMED-OUT` submission; PsyNet has no participant row with timed-out status.
- Prolific has 12 `APPROVED` submissions; PsyNet has 12 approved participant rows.

The count equality for approved rows hides one apparent mismatch: one approved Prolific submission does not appear as a PsyNet participant row, while one PsyNet-approved participant corresponds to a timed-out Prolific submission.

### Matched Rows With Notable Statuses

- Participant `2`, assignment `6a3e810a9b11329e81b89cb2`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `5`, assignment `6a3e81c62b2d5eecb6bb7d61`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `8`, assignment `6a3e8196b2257d390a7e9541`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `11`, assignment `6a3e818549fe004680707f6b`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `14`, assignment `6a3e833d489d3f929cfaff64`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `17`, assignment `6a3e83f6ebff1d88fc6f5fcd`: dashboard `returned`, Prolific `RETURNED`. Expected.
- Participant `4`, assignment `6a3e8191a6fbc404640781d9`: dashboard `approved`, Prolific `TIMED-OUT`. Unexpected and likely important.

### Prolific Submissions Without Dashboard Participant Rows

The following Prolific submissions were not present in the dashboard participant table by `assignment_id`:

- `6a3e8108a53fdf108a8d10de`: Prolific `APPROVED`, worker `6a0211f66d13da71cb35f782`.
- `6a3e813270bd15b05bc6532e`: Prolific `RETURNED`, worker `6a20154fae9922ea377c928e`.
- `6a3e8108ad1faf1ee5ddf6f8`: Prolific `RETURNED`, worker `665c302327136dcdb0c4a2e0`.
- `6a3e81bfcffc589403ad88e1`: Prolific `RETURNED`, worker `65fbe33d38ea0e3701414b61`.

The returned submissions may correspond to workers who never progressed far enough to create a durable PsyNet participant row. The approved submission without a dashboard row is more suspicious and should be investigated against earlier request/recruiter logs if this discrepancy matters for accounting.

## Timeline

- `13:33:39`: Web log reports `Experiment launch complete`.
- `13:33:46`: Prolific draft study created with `"is_custom_screening": false`.
- `13:39:01`: Prolific study published.
- `13:39-13:57`: Participants enter, complete, return, or time out.
- `13:44:44`: Worker checks assignment `6a3e81c62b2d5eecb6bb7d61`, receives Prolific `RETURNED`.
- `13:45:10`: Recruiter submission complete notification for assignment `6a3e822c5c0e63e412b89c8c`, participant `12`.
- `13:46:25`: Recruiter submission complete notification for assignment `6a3e82428f73c9e85e558b86`, participant `13`.
- `13:50:57`: Worker observes assignment `6a3e833d489d3f929cfaff64` changed to `RETURNED`.
- `13:51:08`: Recruiter submission complete notification for assignment `6a3e83892e5f8638fcd09ec0`, participant `15`.
- `13:53:52`: Worker observes assignment `6a3e83f6ebff1d88fc6f5fcd` still `ACTIVE`.
- `13:54:20`: Approval attempt for assignment `6a3e8191a6fbc404640781d9` fails because Prolific status is `TIMED-OUT`.
- `13:55:05`: Worker observes assignment `6a3e83f6ebff1d88fc6f5fcd` changed to `RETURNED`.
- `13:56:27`: Recruiter submission complete notification for assignment `6a3e84b32c77611aa4033066`, participant `18`.
- `13:56:58`: Approval attempt for assignment `6a3e84b32c77611aa4033066` fails because Prolific status is still `ACTIVE`; bonus payment proceeds.
- `13:57:09`: Corrected watcher reports Prolific study status `COMPLETED`.
- `13:57:31`: Final full Dozzle logs downloaded.

## Per-Container Log Findings

### Web

The web container shows normal request flow through ad, consent, timeline, response submission, worker completion, recruiter exit, and the Prolific submission listener. It includes many ordinary static asset requests and scanner-style or browser favicon requests.

No HTTP 500s or web tracebacks were found. The visible 404s are limited to favicon/scanner-style requests and are not product failures.

### Worker

The worker log contains the most important findings.

Finding 1: timed-out Prolific submission approval attempt.

- Assignment: `6a3e8191a6fbc404640781d9`
- Participant: dashboard participant `4`
- Prolific status at approval: `TIMED-OUT`
- Log evidence: `approve_participant_submission for assignment_id '6a3e8191a6fbc404640781d9' failed with error 'Prolific session not yet submitted (current status is 'TIMED-OUT').'`
- Top stack frame: `dallinger/recruiters.py`, `approve_hit`
- Exception: `dallinger.prolific.ProlificServiceException`
- Severity: Medium. The worker explicitly logs that it will proceed anyway, and the study completes. However, the dashboard later shows this participant as `approved`, while Prolific shows `TIMED-OUT`, which is inconsistent.

Finding 2: active Prolific submission approval attempt.

- Assignment: `6a3e84b32c77611aa4033066`
- Participant: dashboard participant `18`
- Prolific status at first approval attempt: `ACTIVE`
- Log evidence: `approve_participant_submission for assignment_id '6a3e84b32c77611aa4033066' failed with error 'Prolific session not yet submitted (current status is 'ACTIVE').'`
- Top stack frame: `dallinger/recruiters.py`, `approve_hit`
- Exception: `dallinger.prolific.ProlificServiceException`
- Severity: Low to Medium. This is a known timing edge case: the participant had completed PsyNet, but Prolific had not yet registered submission. The final Prolific status became `APPROVED`, so this appears to be recovered successfully.

Finding 3: return-for-bonus flows.

- Assignments including `6a3e81c62b2d5eecb6bb7d61`, `6a3e8196b2257d390a7e9541`, `6a3e83f6ebff1d88fc6f5fcd`, and `6a3e833d489d3f929cfaff64` show Prolific return checks and assignment return notifications.
- The dashboard branch logs include `return_for_bonus_enabled` and `assignment_return_result` values.
- Severity: Expected behavior for screen-out/unsuccessful-end paths, but repeated `assignment_return_result=False` before success should remain visible in reports.

Finding 4: bonus payments.

- Bonus payment requests were made for successful participants with non-zero performance rewards.
- The log also explicitly states when a `0.0` bonus was not paid because it was below `0.01`.
- Severity: Expected.

### Clock

The clock log shows periodic recruiter checks, Prolific submission polling, close-recruitment decisions, and `Session idle in transaction!` warnings.

No clock crash, deadlock, or undefined-table error was found.

### Redis

Redis starts successfully and remains available. The standard memory-overcommit warning appears at startup. No Redis failure associated with the deployment was found.

### PgBouncer

PgBouncer starts successfully and records normal connection, idle timeout, and stats entries. The PsyNet/Dallinger logs contain repeated `Session idle in transaction!` warnings involving module/process queries.

Severity: Low unless paired with stuck jobs, deadlocks, or failed requests. In this run, no deadlock or failed request pattern was found, but the repeated idle-transaction warnings should remain tracked because they can point to transaction lifecycle issues.

## Error And Warning Search Summary

Searches and manual tail review found:

- No web HTTP 500s.
- No `UndefinedTable`.
- No `DeadlockDetected`.
- No deployment-stopping crash.
- No failed launch after final successful launch.
- Worker Prolific approval tracebacks for `TIMED-OUT` and `ACTIVE` statuses.
- Repeated `Session idle in transaction!` warnings.
- Scanner/favicon 404s, treated as harmless.

## Open Questions

- Why did dashboard participant `4` end as `approved` when Prolific submission `6a3e8191a6fbc404640781d9` ended as `TIMED-OUT`?
- Why does Prolific submission `6a3e8108a53fdf108a8d10de` show `APPROVED` without a dashboard participant row?
- Are missing dashboard rows for returned Prolific submissions expected when workers return before PsyNet participant creation?
- Should `approve_hit` log known Prolific timing/status cases as warning-only without a full traceback when it explicitly proceeds anyway?

## Recommended Follow-Up

Investigate the participant-status reconciliation around timed-out and pre-participant Prolific submissions. The likely code paths are in Dallinger's Prolific recruiter approval/return handling and PsyNet's participant status synchronization.

Suggested regression coverage:

- A Prolific submission transitions to `TIMED-OUT` after PsyNet completion but before approval; dashboard status should not misleadingly become `approved`.
- A Prolific participant starts/returns before a PsyNet participant row is created; expected dashboard/prolific reconciliation behavior should be explicit.
- `approve_participant_submission` receives `ACTIVE` or `TIMED-OUT`; logs should distinguish expected transient/status cases from true failures.
