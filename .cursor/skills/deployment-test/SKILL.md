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

## Deploy The Test Experiments From The Test Branch

A full deployment test covers two experiments in `tests/deployment`:

- `tests/deployment/payment_flows_prolific`: the basic Prolific recruiter test,
  exercising payment flows (base payment, screen-out compensation, and
  performance rewards).
- `tests/deployment/audio_gibbs`: an audio Gibbs sampler experiment that
  additionally exercises audio synthesis (parselmouth), asset
  generation/storage, async worker processes, and a headphone prescreen.
  Besides the default Prolific configuration, it carries a **Lucid variant**
  (`experiment.py.lucid` + `config.txt.lucid`), used for a third,
  Lucid-recruiter deployment (see "Deploy The Lucid Variant" below).

By default a full deployment test produces **three apps**: the two Prolific
experiments deployed **in parallel** to save wall-clock time, plus the Lucid
variant of `audio_gibbs` deployed right after its Prolific sibling. Deploy a
subset only when the user explicitly asks for it. Prepare both experiment
directories on a **single fresh deployment branch created for this
deployment** (the preparation steps below are shared), then run the two
Prolific `psynet deploy ssh` commands concurrently. Do not reuse or rebase a
long-lived deployment branch; each deployment gets its own branch so its
exact code is preserved for later auditing.

**Base the branch on the latest PsyNet release tag by default** (including
release candidates, e.g. `v13.3.0rc0`), so the test exercises what users
actually install. Base it on `master` only when the user explicitly asks for
a master-based deployment. Always fetch tags first and confirm the chosen
base tag with the user if there is any ambiguity (e.g. an RC and a final tag
for the same version).

Name the branch after the base, e.g. `deployment-tests/v13.3.0rc1`,
appending `-2`, `-3`, ... for repeat deployments from the same base. (Older
deployment branches carry a per-experiment suffix such as `-prolific`; new
branches cover both experiments and drop it.)

Before deploying:

1. Verify the deployment server is reachable before doing any preparation
   work, so connectivity problems surface immediately rather than after the
   branch and pins are already set up. Check both SSH login and the Docker
   daemon on the server:

```bash
ssh -i <ssh-key> -o BatchMode=yes -o ConnectTimeout=10 <ssh-user>@<ssh-host> \
  "docker info --format '{{.ServerVersion}}'"
```

   Success prints the server's Docker version. If the SSH login or the Docker
   check fails, stop and report the failure to the user instead of starting
   the deployment preparation.
2. Verify the recruiter credentials are set up for **both Prolific and
   Lucid** before deploying anything. The Prolific token and the Lucid
   API/hashing keys must be present (typically in `~/.dallingerconfig`);
   commented-out entries count as missing. Check presence without printing
   any values:

```bash
python - <<'PY'
from dallinger.config import get_config

config = get_config()
config.load()
for key in ["prolific_api_token", "lucid_api_key", "lucid_sha1_hashing_key"]:
    try:
        status = "set" if config.get(key) else "EMPTY"
    except KeyError:
        status = "MISSING"
    print(f"{key}: {status}")
PY
```

   If any credential is missing or empty, stop and ask the user to set it
   before deploying (a missing Lucid key otherwise only surfaces after the
   Lucid app's Docker image is already built, wasting a deploy cycle).
3. Check both repositories for local changes. Do not discard or overwrite user
   work. If either checkout is dirty in a way that affects deployment, stop and
   ask the user how to proceed.
4. Create the deployment branch from the base and import both experiment
   directories from the most recent previous deployment branch, or from
   `master` if it is newer or no previous deployment branch exists (the
   `tests/deployment` directories carry deployment settings that are
   typically not on release tags):

```bash
cd <psynet-root>
git fetch origin master --tags
BASE_TAG=$(git tag --list 'v*' --sort=-v:refname | head -1)  # or the tag the user specifies
echo "Base: $BASE_TAG"
git switch -c deployment-tests/$BASE_TAG "$BASE_TAG"
git checkout <previous-deployment-branch> -- tests/deployment/payment_flows_prolific tests/deployment/audio_gibbs
```

   For an explicitly requested master-based deployment, update local `master`
   (`git switch master && git pull --ff-only origin master`) and branch from
   `master` instead.

   Verify the imported experiment configuration includes the standing
   deployment settings:

   - `payment_flows_prolific/experiment.py`: `prolific_is_custom_screening=False`,
     `auto_recruit=True`, `initial_recruitment_size=12`.
   - `audio_gibbs/experiment.py`: `auto_recruit=True`,
     `initial_recruitment_size=3`, `target_n_participants=5`.
   - `audio_gibbs/experiment.py.lucid`: `initial_recruitment_size=10` equal to
     `target_n_participants=10`, so the Lucid survey is created with its full
     quota (the marketplace UI shows the full expected completes and fields
     to target without PsyNet-side quota top-ups). It also sets
     `wage_per_hour=18` (Lucid's `QuotaCPI` is derived from
     `estimated_max_reward(wage_per_hour)`; the default wage yielded a CPI of
     ~0.5, which converted poorly) and opens with a short plain-language
     welcome page ("4-minute listening study, headphones required, ...")
     before consent to reduce voluntary bounces at entry. The experiment
     also pauses the Lucid survey via the API once the participant target is
     reached (`Exp.recruit` override): Lucid does not reliably stop
     admitting entrants at the quota on its own, and
     `LucidRecruiter.close_recruitment` is a no-op.
   - `audio_gibbs/lucid_recruitment_config.json` carries marketplace
     qualifications that prescreen panelists before they enter PsyNet:
     desktop-only (`MS_is_mobile`/`MS_is_tablet` excluded) and audio
     capability (`HAS_AUDIO v1`). This shifts ineligible participants from
     entry bounces to marketplace screen-outs.
   - All `config.txt` files, including `config.txt.lucid`:
     `publish_experiment = true`.

5. Match Dallinger to the PsyNet base. For a release-tag deployment, check out
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

6. Activate the PsyNet virtual environment and install both local checkouts in
   editable mode so the deployment command is run from the latest local code:

```bash
cd <psynet-root>
source <venv>/bin/activate
echo "$VIRTUAL_ENV"
uv pip install -e <dallinger-root>
uv pip install -e ".[dev,slack]"
```

7. Refresh the experiment template scripts from the installed PsyNet (which
   matches the base after step 6) and commit the result, so the deployment
   image is built with the base version's current templates (Dockerfile,
   `docker/` helpers, `pytest.ini`, etc.). Run this in **each** experiment
   directory being deployed:

```bash
for exp in payment_flows_prolific audio_gibbs; do
  (cd <psynet-root>/tests/deployment/$exp && psynet update-scripts)
done
git add tests/deployment && git commit -m "Refresh experiment scripts via psynet update-scripts"
```

   Review the diff before committing; template changes should be plausible for
   the base version (e.g. pinned image tags matching the base tag).

8. Pin the packages in each experiment's `requirements.txt`
   to match the base (keep the extra `audio_gibbs` dependencies such as
   `praat-parselmouth` and `scipy` in place):

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
9. Regenerate `constraints.txt` from the updated `requirements.txt` in each
   experiment directory before deploying, and commit them. The experiment
   Dockerfile installs from `constraints.txt` when it exists, so a stale file
   would silently override the new pins:

```bash
for exp in payment_flows_prolific audio_gibbs; do
  (cd <psynet-root>/tests/deployment/$exp && psynet generate-constraints)
done
git add tests/deployment/*/constraints.txt && git commit -m "Regenerate constraints from pinned requirements"
```

10. Ensure neither experiment enables `prolific_is_custom_screening`
   (`tests/deployment/payment_flows_prolific/experiment.py` sets it to `False`
   explicitly;
   `audio_gibbs` relies on the `False` default). Prolific no longer supports
   the older custom-screening study creation flow; a launch payload with
   `"is_custom_screening": true` fails with Prolific error `140003`.

Deploy both experiments **in parallel**, each from its own directory with its
own app name. Start each deploy as a background process (or in separate
terminals) and monitor both launch outputs:

```bash
source <psynet-root>/<venv>/bin/activate

cd <psynet-root>/tests/deployment/payment_flows_prolific
psynet deploy ssh \
  --server <ssh-host> \
  --dns-host <dns-host> \
  --app <payment-flows-prolific-app-name> &

cd <psynet-root>/tests/deployment/audio_gibbs
psynet deploy ssh \
  --server <ssh-host> \
  --dns-host <dns-host> \
  --app <audio-gibbs-prolific-app-name> &

wait
```

Do not let one deployment's failure silently abort the other: check each
launch output separately, and report per-app success/failure.

Name each app after the deployment branch, experiment, and recruiter:
`test-<base-tag>-payment-flows-prolific` and
`test-<base-tag>-audio-gibbs-prolific`, appending `-2`, `-3`, ... for repeat
deployments. App names only allow `a-z`, `0-9`, and `-` (the deploy command
rejects anything else), so replace the dots in the base tag with dashes,
e.g. base tag `v13.3.0rc1` gives `test-v13-3-0rc1-payment-flows-prolific-1`
and `test-v13-3-0rc1-audio-gibbs-prolific-1`. (Older deployments used the
app names `test-<base-tag>-prolific` and `test-<base-tag>-audio-gibbs`,
before the recruiter suffix became part of the convention.) After
deployment, inspect each launch output for the experiment URL, dashboard
URL, and Dozzle URL.

## Deploy The Lucid Variant

The full deployment test also includes a third app: the `audio_gibbs`
experiment deployed with the **Lucid recruiter**, exercising the Lucid
recruitment path (`LucidConsent`, `lucid_recruitment_config.json`).

The Lucid variant deploys from the same `tests/deployment/audio_gibbs`
directory, so it cannot start until the Prolific `audio_gibbs` deploy command
has finished (the running Prolific app is unaffected by later file changes).
Start it as soon as that deploy completes, so it runs while the Prolific apps
are being observed.

1. Switch the directory to the Lucid variant and commit the swap, so the
   deployment branch records exactly what was deployed:

```bash
cd <psynet-root>/tests/deployment/audio_gibbs
cp experiment.py.lucid experiment.py
cp config.txt.lucid config.txt
git add experiment.py config.txt
git commit -m "Switch audio_gibbs to Lucid variant for Lucid deployment"
```

2. Deploy with the app name `test-<base-tag>-audio-gibbs-lucid`, appending
   `-2`, `-3`, ... for repeat deployments (e.g.
   `test-v13-3-0rc1-audio-gibbs-lucid-1`):

```bash
psynet deploy ssh \
  --server <ssh-host> \
  --dns-host <dns-host> \
  --app <audio-gibbs-lucid-app-name>
```

3. After the Lucid deploy has launched, restore the Prolific variant and
   commit, so the directory's final state on the deployment branch is the
   default configuration:

```bash
cp experiment.py.prolific experiment.py
cp config.txt.prolific config.txt
git add experiment.py config.txt
git commit -m "Restore Prolific variant after Lucid deployment"
```

Notes for the Lucid app:

- Like the Prolific configs, `config.txt.lucid` sets
  `publish_experiment = true`, so the Lucid survey goes live automatically at
  launch (survey status `03`) instead of requiring manual publication in the
  Lucid marketplace.
- The "Observe Until Prolific Completion" workflow below is
  Prolific-specific. For the Lucid app there is no Prolific study to poll;
  observe the dashboard participant table, recruiter state, and Dozzle logs
  until the target number of participants completes or the user stops the
  test, then apply the same per-app audit-trail workflow (skipping the
  Prolific study/submissions JSON artifact and capturing the equivalent
  Lucid recruiter-state evidence instead).

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
`hit_id`. If you need to read the `hit_id` from the database inside the
container, use raw SQL (e.g.
`SELECT DISTINCT hit_id FROM participant WHERE hit_id IS NOT NULL`) rather
than the Dallinger ORM: querying `Participant` via the ORM from a plain
container Python shell fails with
`No such polymorphic_identity 'psynet.participant.Participant'` because the
PsyNet models are not imported in that context. Then query Prolific like this:

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

When several apps were deployed, observe them in parallel and apply this
whole completion/audit workflow to each app independently: each has its own
recruiter run, its own dashboard, and its own audit folder keyed by app name
(the Lucid app follows the adapted observation described in "Deploy The
Lucid Variant"). Do not stop observing one app because another completed
first.

After the study status is `COMPLETED`, record the deployment's audit trail in
a per-deployment folder on the deployment branch. Each deployment gets one
folder named after the study-completion date/time and app name, containing a
tracked `analysis.md` and a gitignored `local/` subfolder for all raw
artifacts:

```text
deployment-tests/<YYYYMMDD-HHMMSS>-<app-name>/
  analysis.md                            # tracked: the Markdown analysis
  local/                                 # gitignored: raw data, never committed
    logs.zip                             # full Dozzle logs download
    logs/                                # extracted per-container logs
    export/                              # psynet export output
    prolific-study-and-submissions.json  # raw Prolific data
```

Only `analysis.md` is committed. Everything in `local/` contains participant
identifiers and/or bloats git history, and `.gitignore` blocks it from being
tracked. Use local time for the timestamp unless the user requests UTC.

**Never commit sensitive data in `analysis.md` itself.** The analysis is
tracked and pushed, so before committing it, check that it contains none of:

- Prolific worker/participant IDs (`worker_id` / `PROLIFIC_PID` values) or any
  other platform account identifiers.
- Participant personal data: names, demographics, free-text responses, or
  quoted answer content.
- Credentials, API tokens, or secret config values (including anything the
  user supplied for dashboard/Dozzle/SSH login).

Referring to participants by their PsyNet row id (`participant 16`) and to
submissions by Prolific submission/assignment id is fine; those are needed for
cross-referencing and are not personal identifiers. When log excerpts are
quoted, strip any worker IDs they contain. If in doubt, describe the evidence
and point to the `local/` artifact instead of quoting it.

Collect the `local/` artifacts as follows:

1. **Full Dozzle logs**: save the downloaded ZIP as `local/logs.zip` and
   extract it to `local/logs/` (see the Dozzle section below).
2. **Database/data export**: run `psynet export ssh` from the experiment
   directory into `local/export/`:

```bash
cd <psynet-root>/tests/deployment/<experiment>  # the app's experiment dir
psynet export ssh --app <app-name> --server <ssh-host> --anonymize no \
  --path <psynet-root>/deployment-tests/<YYYYMMDD-HHMMSS>-<app-name>/local/export
```

   This saves the database dump (`regular/database.zip`), per-table CSVs
   (`regular/data/`), and the deployed source code (`source_code.zip`).

3. **Raw Prolific data**: save the full study object and all submissions as
   JSON (run the `prolific_service_from_config()` snippet above with
   `print(json.dumps({'study': study, 'submissions': submissions}, ...))`
   and redirect to `local/prolific-study-and-submissions.json`).

### Post-completion checklist

Work through all of these once `study_status == "COMPLETED"`:

1. Download the full Dozzle logs ZIP again and re-run the log review,
   comparing against the deployment-time scan; store it in `local/`.
2. Export the database and data with `psynet export ssh` into `local/export/`.
3. Save the raw Prolific study and submissions JSON into `local/`.
4. Write `analysis.md`, referencing the `local/` artifacts, verify it contains
   no sensitive data (see above), and commit it to the deployment branch.
5. Offer to tear down the deployed app once the data is captured. Do not
   destroy it without explicit user confirmation:

```bash
cd <psynet-root>/tests/deployment/<experiment>  # the app's experiment dir
psynet destroy ssh --server <ssh-host> --app <app-name>
```

This report should be more detailed than the chat summary. Include:

- Deployment metadata: app name, experiment URL, dashboard URL, PsyNet commit,
  Dallinger commit, Prolific study id, and final Prolific study status.
- Final Prolific counts by submission status, including `APPROVED`, `RETURNED`,
  `TIMED-OUT`, `AWAITING REVIEW`, and any unexpected statuses.
- The total cost of the run as reported by the recruiting platform itself.
  Fetch it inside the app's web container: for Prolific apps use
  `ProlificService.get_total_cost(study_id)` (via
  `prolific_service_from_config()`); for Lucid apps use
  `LucidService.get_cost(survey_number)` (via `get_lucid_service()`). Report
  the amount with its currency and state which platform figure it is.
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

If direct `curl -u <dozzle-username>:<dozzle-password>` returns `401`, fetch the ZIP through the authenticated browser session instead; Dozzle uses the browser login session. The download is a ZIP containing one log file per container. For post-completion downloads, save it in the deployment folder's `local/` subfolder:

```text
deployment-tests/<YYYYMMDD-HHMMSS>-<app-name>/local/logs.zip
deployment-tests/<YYYYMMDD-HHMMSS>-<app-name>/local/logs/
```

For throwaway intermediate scans during the run, use a system temp path (e.g.
`/tmp/dozzle-<app-name>/`) so nothing transient lands in the repository.

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
