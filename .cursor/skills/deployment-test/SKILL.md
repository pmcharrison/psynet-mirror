---
name: deployment-test
description: Debug deployed PsyNet test experiments by logging into the PsyNet dashboard and Dozzle logs, inferring the app name from deployment URLs, finding matching containers, and summarizing deployment, web, worker, clock, and recruiter errors. Use when the user asks to debug a deployed PsyNet experiment, inspect Dozzle logs, inspect the PsyNet dashboard, or diagnose a test deployment app such as test-v13-3-0rc0-prolific-1.
---

# Deployment Test

Use this skill for deployed PsyNet test experiments when the user provides an experiment URL, a Dozzle logs URL, an app name, deployment logs, or asks to inspect the dashboard/logs.

## Default URLs And Credentials

- Experiment URL example: `https://test-v13-3-0rc0-prolific-1.experiments1.cococo-lab.cornell.edu/`
- Dashboard path: `/dashboard/`
- Dozzle URL: `https://logs.experiments1.cococo-lab.cornell.edu/`

Credentials are not stored in this skill. Before logging into the PsyNet
dashboard or Dozzle, ask the user to provide:

- the PsyNet dashboard username and password, and
- the Dozzle username and password.

Do not proceed with authenticated steps until the user has supplied them, and
do not record the provided credentials in reports, logs, or committed files.

## Local Environment Inputs

This skill does not hardcode machine-specific paths. Before running local
commands, ask the user for (or confirm from repo-local rules/context):

- `<psynet-root>`: the PsyNet repository root (e.g. `~/PsyNet`).
- `<dallinger-root>`: the Dallinger repository root (e.g. `~/Dallinger`).
- `<venv>`: the name of the PsyNet virtual environment directory inside
  `<psynet-root>`. Default to `.venv` unless the user or a repo-local rule
  specifies otherwise.
- `<ssh-user>@<ssh-host>`: the SSH login for the deployment server (e.g.
  `user@experiments1.cococo-lab.cornell.edu`), and the SSH key path
  `<ssh-key>` if one is required.
- `<dns-host>`: the public DNS host used by deployed experiment URLs. Default
  to `<ssh-host>` when the SSH server and DNS host are the same.

## Python Environment

Always use the PsyNet virtual environment at `<psynet-root>/<venv>` for PsyNet
commands and Python dependency commands. Before running `psynet`, `python`,
`pip`, `uv`, `pytest`, or `pre-commit` from the PsyNet checkout, activate it
and verify it:

```bash
cd <psynet-root>
source <venv>/bin/activate
echo "$VIRTUAL_ENV"
```

If the virtual environment is missing or activation fails, stop and tell the
user before running any PsyNet or Python-related command.

## Deploy The Prolific Test From The Test Branch

When asked to redeploy the Prolific manual recruiter test, deploy
`tests/manual_recruiter_testing/prolific` from a **fresh deployment branch
created for this deployment**. Do not reuse or rebase a long-lived deployment
branch; each deployment gets its own branch so its exact code is preserved
for later auditing.

**Base the branch on the latest PsyNet release tag by default** (including
release candidates, e.g. `v13.3.0rc0`), so the test exercises what users
actually install. Base it on `master` only when the user explicitly asks for
a master-based deployment. Always fetch tags first and confirm the chosen
base tag with the user if there is any ambiguity (e.g. an RC and a final tag
for the same version).

Name the branch after the base, e.g.
`test-deployments/v13.3.0rc0-prolific`, appending `-2`, `-3`, ... for repeat
deployments from the same base.

Before deploying:

1. Check both repositories for local changes. Do not discard or overwrite user
   work. If either checkout is dirty in a way that affects deployment, stop and
   ask the user how to proceed.
2. Create the deployment branch from the base and import the experiment
   configuration from the most recent previous deployment branch, or from
   `master` if it is newer or no previous deployment branch exists (the
   `tests/manual_recruiter_testing/prolific` directory carries deployment
   settings that are typically not on release tags):

```bash
cd <psynet-root>
git fetch origin master --tags
BASE_TAG=$(git tag --list 'v*' --sort=-v:refname | head -1)  # or the tag the user specifies
echo "Base: $BASE_TAG"
git switch -c test-deployments/$BASE_TAG-prolific "$BASE_TAG"
git checkout <previous-deployment-branch> -- tests/manual_recruiter_testing/prolific
```

   For an explicitly requested master-based deployment, update local `master`
   (`git switch master && git pull --ff-only origin master`) and branch from
   `master` instead.

   Verify the imported experiment configuration includes the standing
   deployment settings:

   - `experiment.py`: `prolific_is_custom_screening=False`,
     `auto_recruit=True`, `initial_recruitment_size=12`.
   - `config.txt`: `publish_experiment = true`.

3. Match Dallinger to the PsyNet base. For a release-tag deployment, check out
   the Dallinger version that the PsyNet tag pins in its `pyproject.toml`
   (e.g. the `vX.Y.Z` Dallinger tag satisfying the pin). For a master-based
   deployment, use the latest Dallinger `master`:

```bash
cd <dallinger-root>
git fetch origin master --tags
# Release-tag deployment:
git checkout <dallinger-tag-matching-psynet-pin>
# Master-based deployment:
# git switch master && git pull --ff-only origin master
DALLINGER_SHA=$(git rev-parse HEAD)
```

4. Activate the PsyNet virtual environment and install both local checkouts in
   editable mode so the deployment command is run from the latest local code:

```bash
cd <psynet-root>
source <venv>/bin/activate
echo "$VIRTUAL_ENV"
uv pip install -e <dallinger-root>
uv pip install -e ".[dev,slack]"
```

5. Refresh the experiment template scripts from the installed PsyNet (which
   matches the base after step 4) and commit the result, so the deployment
   image is built with the base version's current templates (Dockerfile,
   `docker/` helpers, `pytest.ini`, etc.):

```bash
cd <psynet-root>/tests/manual_recruiter_testing/prolific
psynet update-scripts
git add . && git commit -m "Refresh experiment scripts via psynet update-scripts"
```

   Review the diff before committing; template changes should be plausible for
   the base version (e.g. pinned image tags matching the base tag).

6. Pin the packages in `tests/manual_recruiter_testing/prolific/requirements.txt`
   to match the base:

   - **Release-tag deployment (default)**: pin PsyNet to the base tag and
     Dallinger to its matching tag, e.g.

     ```text
     dallinger[docker] @ git+https://github.com/Dallinger/Dallinger.git@v12.2.1
     psynet @ git+https://gitlab.com/PsyNetDev/PsyNet.git@v13.3.0rc0
     ```

   - **Master-based deployment**: pin both to the latest pushed `master`
     commit hash. Never pin to a branch name; PsyNet's deploy pre-check
     rejects branch-name requirements as ambiguous.

   Commit the imported/updated experiment configuration and pins, push the
   deployment branch (for auditability), and record the base tag (or master
   commit), the deployment-branch commit, and the Dallinger pin in the final
   report.
7. Regenerate `constraints.txt` from the updated `requirements.txt` before
   deploying, and commit it. The experiment Dockerfile installs from
   `constraints.txt` when it exists, so a stale file would silently override
   the new pins:

```bash
cd <psynet-root>/tests/manual_recruiter_testing/prolific
psynet generate-constraints
git add constraints.txt && git commit -m "Regenerate constraints from pinned requirements"
```

8. Ensure `tests/manual_recruiter_testing/prolific/experiment.py` sets
   `prolific_is_custom_screening` to `False`. Prolific no longer supports the
   older custom-screening study creation flow; a launch payload with
   `"is_custom_screening": true` fails with Prolific error `140003`.

Deploy from the experiment directory:

```bash
cd <psynet-root>/tests/manual_recruiter_testing/prolific
source <psynet-root>/<venv>/bin/activate
psynet deploy ssh \
  --server <ssh-host> \
  --dns-host <dns-host> \
  --app <app-name>
```

Name the app after the deployment branch: `test-<base-tag>-prolific`,
appending `-2`, `-3`, ... for repeat deployments. App names only allow
`a-z`, `0-9`, and `-` (the deploy command rejects anything else), so
replace the dots in the base tag with dashes, e.g. base tag `v13.3.0rc0`
gives `test-v13-3-0rc0-prolific-1`. After deployment, inspect the launch
output for the experiment URL, dashboard URL, and Dozzle URL.

## Infer The App Name

If the user gives an experiment URL, infer the app name from the first hostname segment:

```text
https://test-v13-3-0rc0-prolific-1.experiments1.cococo-lab.cornell.edu/
app name = test-v13-3-0rc0-prolific-1
```

Use the app name to filter Dozzle containers and to identify related logs.

## Browser Workflow

When using browser automation, launch a dedicated browser subagent for dashboard and Dozzle inspection when the task is more than a quick single-page lookup. First inspect current tabs, then navigate or reuse tabs.

1. Open the experiment URL and follow the experimenter dashboard link, or navigate directly to `<experiment-url>/dashboard/`.
2. Log into the PsyNet dashboard with the credentials provided by the user.
3. Verify the dashboard loads. Check the database pages, monitoring page, lifecycle/status pages, and any page the user reported as failing.
4. Open Dozzle at `https://logs.experiments1.cococo-lab.cornell.edu/`.
5. Log into Dozzle with the credentials provided by the user.
6. Search/filter containers by the inferred app name.
7. Inspect all matching containers, especially:
   - `<app>-web-1`
   - `<app>-worker-*`
   - `<app>-clock-*`
   - deployment or one-off launch containers if present

## Dashboard Shortcuts

- The participant table URL must use the fully qualified PsyNet participant polymorphic identity:
  - `<experiment-url>/dashboard/database?table=participant&polymorphic_identity=psynet.participant.Participant`
- Do not use `polymorphic_identity=None` for the `participant` table; it is not a valid dashboard URL for polymorphic participant rows and can produce a 500 from `get_mapped_class()`.
- The recruiter state table URL is:
  - `<experiment-url>/dashboard/database?table=recruiter_state&polymorphic_identity=None`
- When inspecting participant rows, change the page length dropdown to `100` first. If the visible table is still awkward to read, use the DataTables state from the browser console:

```javascript
(() => {
  const dt = window.jQuery("#database-table").DataTable();
  return {
    pageInfo: dt.page.info(),
    rows: dt.rows({ search: "applied" }).data().toArray(),
  };
})();
```

Important fields for the Prolific manual test are: `id`, `worker_id`, `assignment_id`, `hit_id`, `failed`, `failed_reason`, `status`, `complete`, `branch_log`, `failure_tags`, `base_payment`, `performance_reward`, `progress`, and `time_credit`.

## Observe Until Prolific Completion

After deployment, observe the ongoing experiment until it completed on Prolific
instead of stopping at launch success. Poll the dashboard participant table,
recruiter state, and logs until the Prolific participant is complete, failed,
returned, or otherwise reaches a terminal state. Record the participant status,
completion flag, failure fields, payment fields, and any recruiter-state changes
seen during the wait.

Also check the Prolific study state directly from the deployed app/container.
Do not print environment variables or config values, because they may include
the Prolific API token. Instead, call `prolific_service_from_config()` inside
the web container and print only the study status and submission status counts.
The experiment is not complete while the Prolific study status is still
`ACTIVE`, even if there are no currently `ACTIVE` submissions and even if all
visible PsyNet participant rows are terminal. The study as a whole must be in
state `COMPLETED`, not `ACTIVE`.

Use the study id from the deployment output, Prolific study URL, or participant
`hit_id`, then query Prolific like this:

```bash
ssh -i <ssh-key> <ssh-user>@<ssh-host> \
  "docker compose -f ~/dallinger/<app-name>/docker-compose.yml exec -T web python - <<'PY'
import json
from collections import Counter

from dallinger.prolific import prolific_service_from_config

study_id = '<prolific-study-id>'
service = prolific_service_from_config(strict=False)
study = service.get_study(study_id)
submissions = service.get_submissions(study_id)
counts = Counter(s.get('status') for s in submissions)
active = [s.get('id') for s in submissions if s.get('status') == 'ACTIVE']
print(json.dumps({
    'study_status': study.get('status'),
    'places_taken': study.get('places_taken'),
    'total_available_places': study.get('total_available_places'),
    'number_of_submissions': study.get('number_of_submissions'),
    'submission_status_counts': dict(sorted(counts.items())),
    'active_submission_count': len(active),
}, sort_keys=True, indent=2))
PY"
```

Do not declare completion from a single poll with `active_submission_count == 0`.
If the study is still `ACTIVE`, Prolific can still recruit replacement
participants after returns or time-outs. Continue observing until
`study_status == "COMPLETED"`. Treat all other study states as not completed
unless the user explicitly asks to stop watching.

Once the Prolific run reaches a terminal state, perform the post-completion
Dozzle log download and review described below. Compare these logs against the
initial deployment-time scan and call out errors that only appeared after
completion.

After the study status is `COMPLETED`, write a detailed Markdown log-analysis
file in a tracked directory on the deployment branch. Use the app name and the
study-completion date/time in the filename so every deployment keeps its own
audit record, for example:

```text
dev/deployment-tests/log-analyses/<YYYYMMDD-HHMMSS>-<app-name>-log-analysis.md
```

Keep the corresponding downloaded full Dozzle logs ZIP in local storage only,
with the same timestamp and app-name stem so it can be matched to the analysis,
for example:

```text
dev/tmp/deployment-tests/log-analyses/<YYYYMMDD-HHMMSS>-<app-name>-logs.zip
```

Do not commit logs ZIPs or extracted raw logs to the branch; they bloat the git
history. Only the Markdown analysis is added to the branch for each deployment.

Use local time for the timestamp unless the user requests UTC. Do not leave the
analysis only under `dev/tmp`; `dev/tmp` is for downloaded ZIPs and extracted
logs.

This report should be more detailed than the chat summary. Include:

- Deployment metadata: app name, experiment URL, dashboard URL, PsyNet commit,
  Dallinger commit, Prolific study id, and final Prolific study status.
- Final Prolific counts by submission status, including `APPROVED`, `RETURNED`,
  `TIMED-OUT`, `AWAITING REVIEW`, and any unexpected statuses.
- Dashboard-vs-Prolific reconciliation: compare participant rows against
  Prolific submissions using assignment/submission id, worker id, status,
  completion flag, failure fields, payment fields, reward/bonus fields, and
  branch/failure logs. Highlight mismatches or explain why they are expected.
- Detailed log findings by container (`web`, `worker`, `clock`, `redis`,
  `pgbouncer`), including tracebacks, errors, warnings, repeated warning loops,
  unusual status transitions, and suspicious but non-fatal events.
- A concise timeline of important events: launch, study creation, recruitment,
  participant completions/returns/time-outs, approval attempts, bonus payments,
  study completion, and post-completion log download.
- Interpretation and severity for each finding, distinguishing confirmed bugs,
  likely harmless noise, expected Prolific edge cases, and unresolved questions.

Reference the exact downloaded log directory and file names used for the
analysis so the evidence can be rechecked later from the local ZIP.

## Dozzle Full Log Download

Always examine the logs from the downloaded complete Dozzle logs ZIP file instead of relying on the visible stream. Use the visible stream only to find the right containers, merged-log page, and download URL.

After opening the merged stream for the app, use the top-right two-dot menu's `Download` action when working manually. In browser automation, the same ZIP URL is usually present as an anchor whose `href` contains `/api/containers/` and `/download?stdout=1&stderr=1`.

Find it with:

```javascript
Array.from(document.querySelectorAll("a"))
  .map((a) => ({ text: a.innerText.trim(), href: a.href }))
  .filter((a) => a.href.includes("/download"));
```

If direct `curl -u <dozzle-username>:<dozzle-password>` returns `401`, fetch the ZIP through the authenticated browser session instead; Dozzle uses the browser login session. The download is a ZIP containing one log file per container. Save it under a temporary workspace path such as:

```text
dev/tmp/dozzle-<app-name>/logs.zip
dev/tmp/dozzle-<app-name>/extracted/
```

### Dozzle API shortcut

Dozzle's root page may serve the SPA shell without authenticating, but the API
requires the login session cookie. Basic auth is not enough for endpoints such
as `/api/events/stream`.

Use `/api/token` to get a `jwt` cookie:

```bash
mkdir -p /tmp/psynet-dozzle-debug
curl -sS -c /tmp/psynet-dozzle-debug/cookies.txt \
  -b /tmp/psynet-dozzle-debug/cookies.txt \
  -X POST \
  -F "username=<dozzle-username>" \
  -F "password=<dozzle-password>" \
  "https://logs.experiments1.cococo-lab.cornell.edu/api/token"
```

Then sample the Server-Sent Events stream. The initial `containers-changed`
event contains the container list, including `id`, `name`, `host`, `state`, and
Docker Compose labels:

```bash
timeout 12 curl -sS -N \
  -b /tmp/psynet-dozzle-debug/cookies.txt \
  -H "Accept: text/event-stream" \
  "https://logs.experiments1.cococo-lab.cornell.edu/api/events/stream"
```

Filter the `data: [...]` JSON for the app name. To download logs for multiple
containers, join each container as `<host>~<id>` and separate containers with
commas:

```text
https://logs.experiments1.cococo-lab.cornell.edu/api/containers/<host>~<id>,<host>~<id>/download?stdout=1&stderr=1
```

Then unpack it and scan all extracted logs. Expect file names like:

- `<app>-clock-1-<timestamp>.log`
- `<app>-web-1-<timestamp>.log`
- `<app>-worker_1-1-<timestamp>.log`
- `<app>-redis-1-<timestamp>.log`
- `<app>_pgbouncer-<timestamp>.log`

## Log Review Checklist

For each matching container, scan the extracted full log files for:

- Python tracebacks and exception class names.
- HTTP 500s, failed `/launch`, dashboard errors, and failed scheduled jobs.
- Prolific API failures, status verification errors, bonus payment errors, unread-message parsing errors, and assignment-return loops.
- Database errors such as `UndefinedTable`, `DeadlockDetected`, transaction rollbacks, and missing columns/attributes.
- Worker restarts, clock crashes, queue errors, and repeated warning loops.
- Whether the error stopped the deployment or was followed by a successful launch.

Always correlate timestamps across containers. A web traceback during `/launch` may be transient if a later `/launch` succeeds.

After the experiment completes on Prolific, download the full Dozzle logs again
and repeat the log review. Do not rely only on the deployment-time ZIP, because
completion can trigger later recruiter, approval, bonus, assignment-return, and
participant-status jobs. Compare the post-completion logs with the initial scan
and report any new errors separately.

Useful search patterns for downloaded logs:

```text
Traceback|TypeError|AttributeError|RuntimeError|Exception|ERROR|CRITICAL|Internal Server Error| 500 |raised an exception|ProlificServiceException|no assignment data|Session idle|Deadlock|UndefinedTable
assignment_returned|AssignmentReturned|AssignmentAbandoned|approve_participant_submission|bonus|reward|Prolific API request|Close recruitment|launch complete|Launched experiment
```

Interpretation shortcuts:

- `TypeError: sequence item 0: expected str instance, list found` in `Experiment.run_recruiter_checks` points to a PsyNet notifier combine/list bug.
- `We found no assignment data for participant <id> with assignment ID <assignment_id> on Prolific!` should be cross-checked against the participant dashboard row for `status`, `failed`, `failed_reason`, and `failure_tags`.
- `Prolific session not yet submitted (current status is 'ACTIVE')` during `approve_participant_submission` can be non-fatal if the worker continues to pay bonuses and later state is consistent.
- `Session idle in transaction!` warnings are worth noting, but are lower priority unless paired with deadlocks, stuck jobs, or failed requests.
- Scanner-style 404s for random assets and manually probed invalid dashboard URLs are not PsyNet/Dallinger product failures.

## Reporting

Keep the report concise and evidence-based:

- State whether the deployment is currently usable.
- Identify the first real error and the latest repeated error.
- Name the affected container(s).
- Include the relevant exception class and top stack frame.
- Distinguish harmless scanner traffic/404s from PsyNet/Dallinger failures.
- If a code fix is needed, name the likely file/function and propose the minimal regression test.
- Mention the detailed Markdown log-analysis file path created after completion.

Do not ask the user to re-paste logs that are already accessible in Dozzle unless browser login or permissions block access.
