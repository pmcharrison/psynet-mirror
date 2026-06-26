---
name: debug-deployment-test-experiments
description: Debug deployed PsyNet test experiments by logging into the PsyNet dashboard and Dozzle logs, inferring the app name from deployment URLs, finding matching containers, and summarizing deployment, web, worker, clock, and recruiter errors. Use when the user asks to debug a deployed PsyNet experiment, inspect Dozzle logs, inspect the PsyNet dashboard, or diagnose a test deployment app such as fh-test-deployment-1.
---

# Debug Deployment Test Experiments

Use this skill for deployed PsyNet test experiments when the user provides an experiment URL, a Dozzle logs URL, an app name, deployment logs, or asks to inspect the dashboard/logs.

## Default URLs And Credentials

- Experiment URL example: `https://fh-test-deployment-1.experiments1.cococo-lab.cornell.edu/`
- Dashboard path: `/dashboard/`
- Dozzle URL: `https://logs.experiments1.cococo-lab.cornell.edu/`
- PsyNet dashboard credentials for these test deployments: `admin` / `dallinger`
- Dozzle credentials for these test deployments: `dallinger` / `dallinger`

## Python Environment

Always use the PsyNet virtual environment at
`/home/frank/projects/PsyNet/.venv-psynet` for PsyNet commands and Python
dependency commands. Before running `psynet`, `python`, `pip`, `uv`, `pytest`,
or `pre-commit` from the PsyNet checkout, activate it and verify it:

```bash
cd /home/frank/projects/PsyNet
source .venv-psynet/bin/activate
echo "$VIRTUAL_ENV"
```

If `.venv-psynet` is missing or activation fails, stop and tell the user before
running any PsyNet or Python-related command.

## Deploy The Prolific Test From The Test Branch

When asked to redeploy the Prolific manual recruiter test, deploy
`tests/manual_recruiter_testing/prolific` from the dedicated PsyNet branch
`test-deployments/prolific-manual-recruiter`. Keep this branch based on the
latest PsyNet `master`, and use the latest Dallinger `master`.
Always start by updating both local `master` branches to their latest remote
commits before preparing the deployment branch.

Before deploying:

1. Check both repositories for local changes. Do not discard or overwrite user
   work. If either checkout is dirty in a way that affects deployment, stop and
   ask the user how to proceed.
2. Update PsyNet `master`, then switch to the deployment branch and bring it up
   to date with `master`:

```bash
cd /home/frank/projects/PsyNet
git fetch origin master
git switch master
git pull --ff-only origin master
git switch test-deployments/prolific-manual-recruiter
git merge --ff-only master
PSYNET_SHA=$(git rev-parse HEAD)
```

1. Update Dallinger to latest `master`:

```bash
cd /home/frank/projects/Dallinger
git fetch origin master
git switch master
git pull --ff-only origin master
DALLINGER_SHA=$(git rev-parse HEAD)
```

1. Activate the PsyNet virtual environment and install both local checkouts in
   editable mode so the deployment command is run from the latest local code:

```bash
cd /home/frank/projects/PsyNet
source .venv-psynet/bin/activate
echo "$VIRTUAL_ENV"
uv pip install -e /home/frank/projects/Dallinger
uv pip install -e ".[dev,slack]"
```

1. Ensure `tests/manual_recruiter_testing/prolific/requirements.txt` points
   PsyNet at `test-deployments/prolific-manual-recruiter`. Push that branch
   before deploying if the remote build must install PsyNet from GitLab. Record
   the PsyNet branch/commit and Dallinger commit in the final report.
1. Ensure `tests/manual_recruiter_testing/prolific/experiment.py` sets
   `prolific_is_custom_screening` to `False`. Prolific no longer supports the
   older custom-screening study creation flow; a launch payload with
   `"is_custom_screening": true` fails with Prolific error `140003`.

Deploy from the experiment directory:

```bash
cd /home/frank/projects/PsyNet/tests/manual_recruiter_testing/prolific
source /home/frank/projects/PsyNet/.venv-psynet/bin/activate
psynet deploy ssh \
  --server experiments1.cococo-lab.cornell.edu \
  --dns-host experiments1.cococo-lab.cornell.edu \
  --app <app-name>
```

Use an app name that encodes the test condition, for example
`fh-test-deployment-<n>`. After deployment, inspect the launch
output for the experiment URL, dashboard URL, and Dozzle URL.

## Infer The App Name

If the user gives an experiment URL, infer the app name from the first hostname segment:

```text
https://fh-test-deployment-1.experiments1.cococo-lab.cornell.edu/
app name = fh-test-deployment-1
```

Use the app name to filter Dozzle containers and to identify related logs.

## Browser Workflow

When using browser automation, launch a dedicated browser subagent for dashboard and Dozzle inspection when the task is more than a quick single-page lookup. First inspect current tabs, then navigate or reuse tabs.

1. Open the experiment URL and follow the experimenter dashboard link, or navigate directly to `<experiment-url>/dashboard/`.
2. Log into the PsyNet dashboard with `admin` / `dallinger`.
3. Verify the dashboard loads. Check the database pages, monitoring page, lifecycle/status pages, and any page the user reported as failing.
4. Open Dozzle at `https://logs.experiments1.cococo-lab.cornell.edu/`.
5. Log into Dozzle with `dallinger` / `dallinger`.
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

## Dozzle Full Log Download

Always examine the logs from the downloaded complete Dozzle logs ZIP file instead of relying on the visible stream. Use the visible stream only to find the right containers, merged-log page, and download URL.

After opening the merged stream for the app, use the top-right two-dot menu's `Download` action when working manually. In browser automation, the same ZIP URL is usually present as an anchor whose `href` contains `/api/containers/` and `/download?stdout=1&stderr=1`.

Find it with:

```javascript
Array.from(document.querySelectorAll("a"))
  .map((a) => ({ text: a.innerText.trim(), href: a.href }))
  .filter((a) => a.href.includes("/download"));
```

If direct `curl -u dallinger:dallinger` returns `401`, fetch the ZIP through the authenticated browser session instead; Dozzle uses the browser login session. The download is a ZIP containing one log file per container. Save it under a temporary workspace path such as:

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
  -F "username=dallinger" \
  -F "password=dallinger" \
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

Do not ask the user to re-paste logs that are already accessible in Dozzle unless browser login or permissions block access.
