# fh-test-deployment-2 log analysis

## Deployment metadata

- App name: `fh-test-deployment-2`
- Experiment URL: `https://fh-test-deployment-2.experiments1.cococo-lab.cornell.edu/`
- Dashboard URL: `https://fh-test-deployment-2.experiments1.cococo-lab.cornell.edu/dashboard`
- Prolific study ID: `6a3ef3528fff6ce12e0e4bcf`
- PsyNet commit installed in Docker image: `8295eeaa18703d09962d8db3e978564170e173c9`
- Dallinger commit installed in Docker image: `5146364a46ce6d3c9b42c63081983c8eb40900ad`
- Log ZIP: `dev/deployment-log-analyses/20260626-182919-fh-test-deployment-2-logs.zip`
- Extracted working copy used for analysis: `dev/tmp/dozzle-fh-test-deployment-2/extracted/`
- Final observed Prolific study status: `AWAITING REVIEW`

This run did not reach Prolific `COMPLETED`. Monitoring was stopped after the study plateaued at `AWAITING REVIEW` with one submission still awaiting review and a matching local participant still marked `working`.

## Final observed counts

Final direct Prolific poll:

- `study_status`: `AWAITING REVIEW`
- `places_taken`: `12`
- `total_available_places`: `12`
- `number_of_submissions`: `18`
- Submission statuses:
  - `APPROVED`: `11`
  - `AWAITING REVIEW`: `1`
  - `RETURNED`: `6`

Final local participant status counts:

- `approved`: `11`
- `returned`: `4`
- `working`: `1`

The difference between 18 Prolific submissions and 16 local participant rows is consistent with some returned submissions occurring before a local PsyNet/Dallinger participant row was created. The remaining important mismatch is the one Prolific `AWAITING REVIEW` submission whose local participant row exists but remains `working`.

## Main finding

One participant reached the failed prescreening path but was not reconciled to a terminal local/recruiter status.

Evidence:

- Prolific submission `6a3ef9...f94a` started at `2026-06-26T22:11:40.708Z` and completed at `2026-06-26T22:15:21.538Z`.
- Prolific status for that submission changed from `ACTIVE` to `AWAITING REVIEW`.
- Matching local participant `14` had:
  - `status`: `working`
  - `failed`: `true`
  - `failed_reason`: `UnsuccessfulEndPage`
  - `complete`: `false`
  - `time_credit`: `131.5`
  - `end_time`: `null`
- Worker logs show repeated status polling for this assignment:
  - `22:14:14`, `22:14:34`, `22:14:53`, `22:15:01`: status `ACTIVE`
  - `22:15:37`, `22:15:45`, `22:16:06`: status `AWAITING REVIEW`
- Unlike other failed-prescreening participants, there was no subsequent `Taking corrective action ... AssignmentReturned` log for participant `14`.

Interpretation: this looks like a reconciliation/status-transition bug for a failed participant whose Prolific submission reaches `AWAITING REVIEW` rather than `RETURNED`. It leaves the Prolific study stuck in `AWAITING REVIEW` and the local participant stuck as `working`.

## Timeline

- `21:46:50`: Experiment launched successfully.
- `21:46:54`: Prolific study creation request used `total_available_places: 12` and `is_custom_screening: false`.
- `21:46:58`: Study `6a3ef3528fff6ce12e0e4bcf` published on Prolific.
- `21:49:51`: Poll showed `5` submissions, `3 ACTIVE`, `1 APPROVED`, study `ACTIVE`.
- `21:56:35`: Poll showed `7 APPROVED`, `4 RETURNED`, no active submissions, but study still `ACTIVE`.
- `22:15:55`: Poll showed `11/12` places taken, `9 APPROVED`, `1 AWAITING REVIEW`, `1 ACTIVE`, `6 RETURNED`.
- `22:19:54`: Poll showed `12/12` places taken and study moved to `AWAITING REVIEW`.
- `22:27:24`: Final direct poll still showed study `AWAITING REVIEW` with `11 APPROVED`, `1 AWAITING REVIEW`, `6 RETURNED`.

## Log findings

### Web

- Launch succeeded and the study was published.
- The launch request initially hit transient TLS errors before succeeding; the final `/launch` returned HTTP 200.
- There are scanner-style 404s for paths such as `/.env`, `/config`, `/wp-json/`, and `/xmlrpc.php`; these are unrelated internet scanner traffic.
- Startup logs contain repeated "A worker restarted" messages during initial gunicorn boot. No later fatal web crash was identified in the downloaded logs.

### Worker

- Normal completions were approved and bonus payments were attempted where expected.
- Several failed-prescreening participants were handled correctly by `AssignmentReturned`.
- Participant `14` is the exception: the logs show Prolific status polling reaching `AWAITING REVIEW`, but no `AssignmentReturned`, no approval, and no terminal local status transition.
- No `ProlificSubmissionNotApprovableError`, `ProlificServiceException`, or Python traceback was found in the downloaded worker log for this run.

### Clock

- Repeated `Session idle in transaction!` warnings were present.
- Some `Experiment._check_barriers` executions were skipped because the maximum number of running instances was reached.
- These are worth noting, but they do not directly explain the participant `14` status mismatch.

### Redis and pgbouncer

- No relevant application-level errors were identified in the downloaded logs.

## Interpretation

The Dallinger Prolific fixes under test did improve/cover returned submissions that Prolific reports as `RETURNED`; those cases were converted locally with `AssignmentReturned`.

This run exposed a different case: a participant can hit PsyNet's unsuccessful end page and still leave Prolific in `AWAITING REVIEW`. The local participant remains `working`, so the study remains stuck at `AWAITING REVIEW` rather than completing.

The likely follow-up area is the failed participant completion path around `UnsuccessfulEndPage`, Prolific screen-out/return handling, and recruiter submission completion/status verification. A focused regression test should cover a participant marked `failed=True` with `failed_reason='UnsuccessfulEndPage'` whose Prolific submission is `AWAITING REVIEW`, asserting that Dallinger either screens out/returns the submission or marks the local participant terminally instead of leaving it `working`.
