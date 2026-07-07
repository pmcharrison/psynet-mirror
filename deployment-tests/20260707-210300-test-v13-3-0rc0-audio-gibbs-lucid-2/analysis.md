# Deployment Log Analysis: test-v13-3-0rc0-audio-gibbs-lucid-2

## Deployment Metadata

- App name: `test-v13-3-0rc0-audio-gibbs-lucid-2`
- Experiment: `tests/deployment/audio_gibbs`, **Lucid recruiter variant**
  (`experiment.py.lucid` + `config.txt.lucid`), second Lucid deployment of
  this experiment (supersedes `test-v13-3-0rc0-audio-gibbs-lucid-1`, which
  was stopped manually after slow fielding)
- Experiment URL: `https://test-v13-3-0rc0-audio-gibbs-lucid-2.experiments1.cococo-lab.cornell.edu/`
- Dashboard URL: `https://test-v13-3-0rc0-audio-gibbs-lucid-2.experiments1.cococo-lab.cornell.edu/dashboard/`
- Deployment branch: `deployment-tests/v13.3.0rc0` (Lucid-variant swap
  committed as `bc0e301b7`, Prolific variant restored as `194d37cb9`)
- PsyNet pin: `v13.3.0rc0`; Dallinger pin: `v12.2.1`
- Lucid survey number: **`80905292`** (lucid-1 used `80899972`)
- Launched ~20:26Z, published live automatically (`publish_experiment=true`)
- This run carried the new conversion improvements: marketplace
  qualifications (desktop-only, `HAS_AUDIO v1`), a plain-language welcome
  page before consent, and a higher CPI ($0.79, from `wage_per_hour=18`).

## Total Cost (Lucid-reported)

`LucidService.get_cost(80905292)`: **$17.58 USD total** ($11.06 sample +
$6.30 fee), 14 completes, **$1.26 per complete**.

## Final Lucid State

- Survey status: `complete` (set explicitly via API; see below)
- Quota record: `Total` quota 10, `Completes` 14, `Prescreens` 63
- 111 entrants, 63 marketplace screens, 14 completes

## Dashboard-vs-Lucid Reconciliation

52 PsyNet participant rows; 14 with `complete=true` (11 `approved`, 3
`submitted` at capture time), matching Lucid's 14 completes exactly. The
remainder: 34 `returned` and 4 `working` (in-flight at capture; they will
time out or finish without affecting the complete count cap).

Failed-participant reasons: 17 `user-tried-to-leave`, 7
`first-response-timeout`, 5 `no-focus-timeout-10s`, 4
`inactivity-timeout-60s`, 1 `overall-timeout-600s`.

## Conversion Comparison With lucid-1

The three conversion improvements were validated dramatically:

| | lucid-1 (baseline) | lucid-2 (improved) |
|---|---|---|
| Entrant-to-complete | 3 of 109 (~3%) over ~3 h | 14 of 111 (~13%) in ~25 min |
| CPI | $0.50 | $0.79 |
| Voluntary leave at entry | dominant (50 of 68 failures) | reduced (17 of 34 failures) |

## Findings

1. **Lucid did not promptly stop admitting entrants at the quota.** Lucid's
   own `Total` quota record ended at 14 completes against a quota of 10
   while the survey stayed `live`; 24 new entrants were admitted in the five
   minutes after the quota was already exceeded (87 -> 111 entrants while
   completes were >= 13). The survey was paused manually at ~20:53Z and set
   to `complete` at ~20:59Z. `LucidRecruiter.close_recruitment` is a no-op
   (it assumes Lucid stops at the quota), so nothing on the PsyNet side
   stopped fielding either. Mitigation added for future runs: the Lucid
   variant now overrides `Exp.recruit` to set the survey to `complete` via
   the API once the participant target is reached (commit `29c33d86c` on
   the MR branch). Overshoot cost: 4 extra completes, ~$5 including fees.
2. **Four gunicorn web workers were OOM-killed** ("Worker (pid:N) was sent
   SIGKILL! Perhaps out of memory?") between 20:43Z and 20:46Z, the peak
   concurrency window (~10+ simultaneous participants, each trial spawning
   `n_jobs=8` parallel synthesis processes). Gunicorn respawned each worker
   immediately and no participant-facing failures or lost completes are
   attributable to it (no HTTP 500s in the log), but it indicates the
   combination of high participant concurrency and parallel parselmouth
   synthesis pressures memory on the shared server. Worth watching in
   future runs; consider lowering `n_jobs` if it recurs at scale.
3. Otherwise clean: no tracebacks in web/worker/clock logs, no Prolific/Lucid
   API failures, no database errors.

## Timeline

- 20:23Z deploy started (Lucid variant swapped in on the deployment branch).
- 20:26Z launched; survey 80905292 created live with quota 10, CPI $0.79,
  and the marketplace qualifications applied.
- 20:30-20:51Z fielding: very fast conversion (5 completes by 20:41Z, 13 by
  20:46Z, 14 by 20:51Z); entrants continued arriving past the quota.
- 20:53Z survey paused manually via API (status `pending`).
- 20:59Z survey set to `complete` via API.
- 21:03Z logs, exports, and Lucid state captured.

## Interpretation / Verdict

The Lucid recruitment path works end-to-end on `v13.3.0rc0` with real
panelists: entry, consent, headphone prescreen, audio Gibbs trials, and
submission/approval all functioned, and the run reconciles exactly (14 = 14).
The two findings are platform/behavioral rather than release regressions:
the quota-overshoot is longstanding Lucid recruiter behavior (now mitigated
in the test experiment), and the OOM worker kills are a server-capacity
observation under an unusually fast, concurrent run.

**Verdict: this run supports promoting `v13.3.0rc0`.**

## Artifacts

- `local/logs/` — full container logs (web, worker_1, clock, redis,
  pgbouncer).
- `local/export/` — `psynet export ssh` output (database, per-table data,
  deployed source code).
- `local/lucid-survey-state.json` — final Lucid summary, quota record, cost
  breakdown, and the full participant table with failure reasons.
