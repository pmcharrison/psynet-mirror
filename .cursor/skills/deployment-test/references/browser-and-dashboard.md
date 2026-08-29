# Browser workflow and dashboard shortcuts


If the user gives an experiment URL, infer the app name from the first hostname segment:

```text
https://test-v13-3-0rc0-prolific-1.experiments1.cococo-lab.cornell.edu/
app name = test-v13-3-0rc0-prolific-1
```

Use the app name to filter Dozzle containers and to identify related logs.

## Credentials

Look these up locally. Do not ask the user to paste passwords, tokens, or
API keys unless the sources below are missing or login fails. Never print the
values, put them in `analysis.md`, or commit them.

### Dashboard

The experimenter dashboard uses HTTP basic auth. The username and password
are the deployer's `dashboard_user` and `dashboard_password`.

1. Read `~/.dallingerconfig`, section `[Dashboard]`, keys `dashboard_user`
   and `dashboard_password`. Check presence only:

```bash
python - <<'PY'
import configparser
from pathlib import Path

cfg = configparser.ConfigParser()
path = Path.home() / ".dallingerconfig"
cfg.read(path)
section = "Dashboard" if cfg.has_section("Dashboard") else "DEFAULT"
user = cfg.get(section, "dashboard_user", fallback="")
password = cfg.get(section, "dashboard_password", fallback="")
print(f"dashboard_user: {'set' if user else 'MISSING'}")
print(f"dashboard_password: {'set' if password else 'MISSING'}")
PY
```

2. If that file has no Dashboard section, use the same keys from
   `dallinger.config.get_config()` after `config.load()`, still printing
   only `set` / `MISSING`.
3. The same pair is also printed at the end of `psynet deploy ssh` on the
   line that starts `You can now log in to the console at` and includes
   `(user = ..., password = ...)`. Prefer the config file; use the deploy
   terminal only as a fallback for that app.

Those values are what the live app was launched with. Use them for
`<experiment-url>/dashboard/` and for authenticated HTTP checks.

### Dozzle

Dozzle is host-level (`https://logs.experiments1.cococo-lab.cornell.edu/`),
not per-app, and is **not** stored in `~/.dallingerconfig` by default.

Read the credentials from the same `psynet deploy ssh` output: the line
`To view the logs for this experiment go to https://logs.... (user = ..., password = ...)`.
Any successful deploy to that server prints the host Dozzle pair. Extract
the values in a script and pass them to `/api/token` or the login form; do
not echo the line into chat.

If no deploy terminal is available, SSH to the server and inspect how
Dozzle is configured there (compose or reverse-proxy auth). Ask the user
only if that also fails.

### Recruiter tokens

Prolific and Lucid keys also live in `~/.dallingerconfig`. Presence-check
them as in `references/deploy-from-test-branch.md` (`prolific_api_token`,
`lucid_api_key`, `lucid_sha1_hashing_key`) without printing values.

## Browser Workflow

When using browser automation, launch a dedicated browser subagent for dashboard and Dozzle inspection when the task is more than a quick single-page lookup. First inspect current tabs, then navigate or reuse tabs.

1. Open the experiment URL and follow the experimenter dashboard link, or navigate directly to `<experiment-url>/dashboard/`.
2. Log into the PsyNet dashboard with the Dashboard credentials from
   `~/.dallingerconfig` (see Credentials above).
3. Verify the dashboard loads. Check the database pages, monitoring page, lifecycle/status pages, and any page the user reported as failing.
4. Open Dozzle at `https://logs.experiments1.cococo-lab.cornell.edu/`.
5. Log into Dozzle with the host credentials from the deploy output
   (see Credentials above).
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
