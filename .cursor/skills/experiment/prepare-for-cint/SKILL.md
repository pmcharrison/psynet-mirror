---
name: prepare-for-cint
description: Prepare a PsyNet experiment for Cint/Lucid recruitment by adding required recruiter settings, locale and wage parameters, qualification-generation tooling, and readiness validation.
authors: [elif22]
---

# Prepare for Cint

Use this skill when the user asks to make an existing PsyNet experiment ready
for Cint/Lucid recruitment. The deliverable is an applied, committed experiment
change plus a Cint Readiness Report, not a live EC2/SSH deployment.

This skill owns Cint/Lucid recruiter parameters and qualification files. For
translation marking or POT extraction, use `prepare-for-translation`. For server
provisioning, SSH deployment, export, app destruction, or EC2 teardown, use
`psynet-deployment-ops`.

## Required reads

- Read the target experiment's `experiment.py`, `config.txt`,
  `requirements.txt`, existing `qualifications/`, `locales/`, and deployment
  notes before editing.
- Inspect any existing `create_qualifications.py`, `qualifications.py`, or
  Lucid/Cint helper scripts. Preserve existing entries and comments.
- Locate this skill's directory from the active skills tree (for example
  `.cursor/skills/experiment/prepare-for-cint` in the PsyNet source tree, or
  `.cursor/skills/psynet/prepare-for-cint` in an experiment skill bundle).
- Read `<skill-dir>/references/create_qualifications_template.py`
  before creating a new qualification-generation script.
- Read `<skill-dir>/assets/example_lucid_ENG_GB.json` as a
  shape example for generated Lucid qualification JSON. Do not treat it as a
  deployable qualification file for the target experiment.

## Workflow

### Phase 1 - Deployment context

Collect and maintain a small in-memory deployment context. Ask the user for any
missing required values before editing target-specific qualification settings:

- experiment short ID;
- deployment targets as language-country pairs;
- PsyNet locale for each target;
- Lucid language and country tags for each target;
- requested Lucid qualifications;
- per-target `wage_per_hour` review value, which may remain blank until the
  experimenter fills it from an approved wage source;
- generated qualification files;
- deployment CSV path, usually `cint_deployment_targets.csv`.

Use English-United Kingdom (`locale = en`, `LANGUAGE = "ENG"`,
`COUNTRY = "GB"`) as the current structural placeholder in `experiment.py`.
Do not ask which placeholder target to use. Real deployment targets still go in
`cint_deployment_targets.csv` and generated qualification files.

Before asking for choices, show this exact explanation verbatim. Do not shorten
it, skip parts, or adapt the examples. The goal is that every user gets the same
baseline Cint deployment explanation before making choices:

```text
Before I prepare the Cint files, here is what you need to decide and why.

Important: this process goes most smoothly when translation readiness is done
first. Before final Cint deployment, make sure every target language has a
reviewed locale file, for example locales/fr/LC_MESSAGES/experiment.po. If
translations are missing, I can still prepare the Cint files, but I will warn
you and tell you which psynet translate command to run later.

1. Target language-country pairs
   Each Cint deployment targets one language-country pair, for example
   Turkish-Turkey or English-United Kingdom. I will add the settings that connect
   the experiment to that target:
   - locale controls the participant-facing experiment language, such as tr or
     en;
   - LANGUAGE tells Cint/Lucid which language market to recruit from, such as
     TUR or ENG;
   - COUNTRY tells Cint/Lucid which country market to recruit from, such as TR
     or GB;

   Before each deployment, locale, LANGUAGE, COUNTRY, and wage_per_hour must be
   set to the correct values for that deployment target. These values are not
   one-time setup values: they must be checked and changed for every separate
   deployment. I will save the target values in cint_deployment_targets.csv so
   you can review and reuse them easily.

2. Qualifications
   A qualification is a Cint/Lucid screening rule. Some rules are technical
   defaults, like blocking mobile/tablet devices or warning about timeouts.
   Custom qualifications ask participants extra eligibility questions. More
   filters can improve sample fit, but they can reduce the number of eligible
   participants and change the expected incidence rate.

   I will prepare create_qualifications.py for the targets and filters you
   choose. You will run that file later in your local repo terminal to generate
   the real JSON files, because real generation needs valid Lucid API keys. I
   cannot honestly generate real Cint/Lucid qualification JSON files unless
   those API keys are already configured in the environment.

3. Wage per hour
   wage_per_hour is the minimum hourly payment value used by PsyNet/Dallinger.
   It is usually determined from online wage or minimum-wage sources and should
   be reviewed separately for each country. I will create
   cint_deployment_targets.csv with a wage_per_hour column so you can fill or
   review wages before each deployment. Do not assume one wage works for every
   country.

4. Cint timing and incidence settings
   I will add recruiter_settings = get_lucid_settings(...). These defaults may
   need adjustment for your study:
   - termination_time_in_s: maximum total time a participant can spend.
   - debug_recruiter: keep False for real deployment; only True for local tests.
   - initial_response_within_s: time allowed before the first response.
   - inactivity_timeout_in_s: timeout after no clicking, typing, scrolling, or
     mouse movement.
   - no_focus_timeout_in_s: timeout after leaving the window or opening a tab.
   - bid_incidence: expected percentage of respondents who qualify after
     targeting and filters. Stricter qualifications usually lower incidence.

5. Qualification options
   TIMEOUT warns participants that leaving the page or switching context can
   terminate participation. PsyNet's Lucid helper adds this automatically.

   MONOLINGUALISM asks whether participants were raised with only their native
   language. Use it only when monolingual background is important, because it can
   strongly restrict the pool.

   HAS_AUDIO asks whether participants can play audio. Use it for audio or music
   experiments.

   ALLOW_VOICE_RECORDING asks whether participants can record their voice. Use it
   only when the study records speech or singing.

   BORN_IN_COUNTRY asks whether participants were born in the target country. Use
   it when birthplace matters for cultural exposure.

   LIVE_IN_COUNTRY asks whether participants currently live in the target
   country. Use it when current residence matters.

   HAS_NATIONALITY asks whether participants hold the target country's
   nationality. Use it when citizenship or nationality matters.

   IS_NATIVE asks whether participants are native speakers of the target
   language. Use it when native-language competence is important.

Now please answer:
1. Which language-country pairs do you want to prepare for Cint?
2. Which qualifications do you want enabled? Select zero or more:
   - MONOLINGUALISM
   - HAS_AUDIO
   - ALLOW_VOICE_RECORDING
   - BORN_IN_COUNTRY
   - LIVE_IN_COUNTRY
   - HAS_NATIONALITY
   - IS_NATIVE

   TIMEOUT is added automatically by PsyNet's Lucid helper and does not need to
   be selected. If you are unsure, tell me what the experiment measures and I
   will suggest a minimal set.

After I edit the repo, I will summarize which files I changed, which target is
currently active in experiment.py (always ENG-GB unless you later change it for
a deployment), which deployment rows need wage review, and
the exact local command you should run to generate real qualification JSON files
once your Lucid API keys are available.
```

If the user is unsure about qualifications after reading the fixed explanation,
ask what the experiment measures and suggest a minimal set. For example, for an
audio/music native-language study, suggest `HAS_AUDIO` and `IS_NATIVE`, then ask
for confirmation.

If targets are unknown, continue with generic parameter preparation and
qualification tooling, but leave real `country_language_tags` commented out and
mark target-specific deployment readiness as incomplete. Do not invent
languages, countries, locales, wages, or real qualification files.

### Phase 2 - Verify Cint prerequisites

1. Verify the experiment can be made Cint-ready without changing its scientific
   logic, timeline, assets, database settings, custom variables, or data schemas.
2. Determine locale codes from PsyNet's supported locales; do not guess. If a
   target locale is missing, stop target-specific readiness and report it.
3. Verify `locales/<locale>/LC_MESSAGES/experiment.po` exists for every known
   target locale. Do not run translation generation in this skill. If one or
   more target `.po` files are missing, do not stop Cint parameter preparation:
   warn the experimenter, list the missing locale files, give the exact
   `psynet translate <locale> ...` command they should run later, and proceed
   without activating those missing locales in `experiment.py`.
4. Determine Lucid language-country tags. First advise the experimenter to run
   `psynet lucid locale` in an environment with valid Lucid API access and use
   that API-backed lookup as the source of truth. If Lucid API access is missing,
   derive provisional tags from local PsyNet Lucid tag references, existing
   qualification templates, and the requested language/country names; clearly
   mark these tags as unverified, report that they are not guaranteed to be
   valid market pairs, and keep target-specific readiness blocked until the
   experimenter verifies them with `psynet lucid locale` or generates real
   qualification JSON successfully.
5. Leave per-target wage values blank in the report unless the user provides an
   approved wage source, commonly `minimum_wage_countries.csv`. Never guess wage
   values. The report should teach the experimenter that `wage_per_hour` must be
   reviewed and set separately for each deployment target.
6. Create or update `cint_deployment_targets.csv` in the experiment root. Include
   one row per requested target and leave `wage_per_hour` blank unless an
   approved wage value was provided. If no targets are known yet, create the file
   with the header only and report that target rows remain blocked.

Required CSV columns:

```text
locale,language,country,language_tag,country_tag,wage_per_hour,qualification_file
```

Use `<skill-dir>/assets/cint_deployment_targets_template.csv`
as the starting point when creating this file.

### Phase 3 - Add Cint parameters to `experiment.py`

Make the smallest safe edit.

1. Add the import if missing:
   `from psynet.recruiters import get_lucid_settings`.
2. Add or update module-level target constants:
   `LANGUAGE = "ENG"`, `COUNTRY = "GB"`, and
   `LUCID_CONFIG_PATH = f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"`.
   Use ENG-GB as the structural placeholder in `experiment.py`; do not ask the
   user to choose another placeholder. The f-string path should resolve to the
   real deployable path for whichever `LANGUAGE` and `COUNTRY` values are active,
   not a mock file. If the real API-generated file is not available yet, copy the
   provided Lucid JSON shape example to the ENG-GB path as a temporary
   placeholder and clearly report that the experimenter must regenerate it
   locally with valid Lucid API access before deployment.
3. Add or update `recruiter_settings = get_lucid_settings(...)` with explicit
   timeouts, `debug_recruiter`, and `bid_incidence`.
   A typical starting block is:

   ```python
   recruiter_settings = get_lucid_settings(
       lucid_recruitment_config_path=LUCID_CONFIG_PATH,
       termination_time_in_s=120 * 60,  # Maximal time a participant can spend.
       debug_recruiter=False,  # Only True during local testing.
       initial_response_within_s=180,  # Terminate if first response is too slow.
       inactivity_timeout_in_s=15 * 60,  # No clicking/typing/scrolling/mouse movement.
       no_focus_timeout_in_s=10 * 60,  # Mouse outside window or another tab.
       bid_incidence=30,  # Percent expected to qualify after targeting.
   )
   ```

   Preserve existing local values when present, but tell the user these are
   study-specific and may need adjustment.
4. Merge Cint keys into the class-level `Exp.config` dictionary. Keep `config`
   inside `class Exp(...)`; do not move it to module scope.
5. Required keys are:
   - `"recruiter": "lucid"`;
   - `"locale": "<target locale>"`;
   - `**recruiter_settings`;
   - `"wage_per_hour": <approved or placeholder wage>`;
   - `"publish_experiment": True`.
6. Preserve existing config keys such as `supported_locales`, storage settings,
   custom variables, and database settings. If multiple target locales are
   planned and their `.po` files already exist, include them in
   `supported_locales`. If `.po` files are missing, keep only the structural
   placeholder locale active, proceed with Cint scaffolding, and report the
   missing translation command instead of generating translations here.

If no real target is known, keep the ENG-GB placeholder constants so the
experiment can import locally, and report that the experiment is Cint-parameter
ready but not target-ready. Keep the computed real-path default visible so the
experimenter knows what must be generated for deployment.

Teach the experimenter that these `get_lucid_settings` parameters are
study-specific review points:

- `lucid_recruitment_config_path`: uses `LUCID_CONFIG_PATH`, which is computed
  from the active `LANGUAGE` and `COUNTRY` values and must resolve to that
  target's generated `qualifications/lucid/lucid-<LANGUAGE>-<COUNTRY>.json`.
- `termination_time_in_s`: maximum time a participant may spend in the
  experiment.
- `debug_recruiter`: use `True` only for local testing; use `False` for real
  Cint/Lucid deployment.
- `initial_response_within_s`: terminates participants who do not reach the first
  response quickly enough.
- `inactivity_timeout_in_s`: terminates after no clicking, typing, scrolling, or
  mouse movement for the configured duration.
- `no_focus_timeout_in_s`: terminates after moving outside the window or opening
  another tab for the configured duration.
- `bid_incidence`: expected percentage of respondents who qualify after basic
  demographic targeting; update it for the study's expected screen-in rate.

### Phase 4 - Create qualification tooling

Prefer a script named `create_qualifications.py`. If the experiment already uses
another script name, preserve that name unless there is a strong reason to
standardize.

1. Create or update the script from the reference template in the experiment
   repo root.
2. Populate `country_language_tags` with the user's requested, verified Lucid
   language-country tuples. Leave unused example tuples commented.
3. Enable the exact qualifications explicitly requested by the experimenter in
   `question_answer_dict`. Leave all other filter examples commented. Never
   auto-enable filters such as native language, nationality, audio, or
   monolingualism.
4. Before claiming real qualification generation, verify that the local PsyNet
   environment can access Lucid through configured `lucid_api_key` and
   `lucid_sha1_hashing_key` values. Do not inspect, print, copy, or commit the
   values. If keys are missing or unusable, stop real generation, leave the
   script ready to run, and mark qualification generation as blocked by missing
   Lucid API access.
5. Preserve existing entries in `qualifications_dict`. If PsyNet raises
   `Unknown question TIMEOUT`, add the alias:
   `"TIMEOUT": service.get_qualifications_dict()["TIMEOUT v1"]`.
6. Write real generated files to
   `qualifications/lucid/lucid-<LANGUAGE>-<COUNTRY>.json`.
7. Tell the user to run the script in their local repo terminal after targets,
   qualifications, and Lucid API access are available. The agent may run the
   script only when safe Lucid API access is already configured.

If no real target has been chosen, provide the script with all real target
tuples commented out and report that target-specific qualification generation is
blocked. When the experiment needs a JSON file to import structurally before
API-backed qualification generation is possible, copy the ENG-GB example JSON
shape to the current `LUCID_CONFIG_PATH` filename. Do not add alternate mock
parameters or `mock-lucid-*` paths in `experiment.py`; instead, remind the user
that this placeholder file must be regenerated in their local repo terminal with
valid Lucid API keys before deployment.

### Phase 5 - Validate readiness

For every known target, verify:

- `LANGUAGE` and `COUNTRY` match the Lucid tags from `psynet lucid locale`;
- `"locale"` matches a PsyNet supported locale;
- `LUCID_CONFIG_PATH` is computed from `LANGUAGE` and `COUNTRY` and resolves to
  the target's generated qualification JSON;
- the qualification JSON exists under `qualifications/lucid/`;
- `wage_per_hour` comes from the approved wage source;
- `locales/<locale>/LC_MESSAGES/experiment.po` exists, or the report warns that
  translations are missing and gives the required `psynet translate ...`
  command;
- `python create_qualifications.py` succeeds when real targets are configured;
- the experiment's normal construction or local test command still runs.

### Phase 6 - Explain Cint deployment review points

Every run must include a short, plain-language explanation for experimenters who
are new to Cint/Lucid deployment. Keep it concise, but do not assume they already
know why these values matter:

- `locale`: controls PsyNet's participant-facing language. It must match an
  existing translation file such as `locales/tr/LC_MESSAGES/experiment.po`.
  Missing translation files should not block Cint parameter scaffolding, but the
  report must warn that deployment for those languages requires running
  `psynet translate <locale> ...` and reviewing the generated `.po` files before
  launch.
- `LANGUAGE` and `COUNTRY`: Lucid/Cint tags for the recruitment market. They
  must match the active deployment target; `LUCID_CONFIG_PATH` is computed from
  these values to select the generated JSON filename. Verify language-country
  tags with `psynet lucid locale` in an environment with Lucid API access when
  possible. If credentials are unavailable, any locally derived tags are
  provisional and must be reported as unverified.
- `wage_per_hour`: the hourly payment rate. Review it separately for every
  country; do not reuse one country's wage for all deployment targets.
- `qualification_file`: the JSON file Cint/Lucid uses for demographic and custom
  qualification targeting. A copied placeholder can support structural review,
  but real deployment needs JSON regenerated with `python create_qualifications.py`
  after valid Lucid API access is configured.
- `create_qualifications.py`: the local script the experimenter runs to create
  real `qualifications/lucid/lucid-<LANGUAGE>-<COUNTRY>.json` files.
- `debug_recruiter`: use `False` for real Cint/Lucid deployment.
- `bid_incidence`: expected percentage of respondents who qualify after the
  chosen targeting and filters. Review it for each study; stricter filters
  usually lower the qualifying pool.
- Timeouts (`termination_time_in_s`, `initial_response_within_s`,
  `inactivity_timeout_in_s`, `no_focus_timeout_in_s`): study-specific limits for
  total participation time, slow starts, inactivity, and leaving the experiment
  window.

## Cint Readiness Report

End with a concise report that explicitly lists every required step and whether
it is complete, blocked, skipped, or not applicable. Do not collapse blockers
into a single final status; reviewers should see exactly what remains.

Use this structure:

- `Experiment parameters`: imports, `LANGUAGE`, `COUNTRY`,
  `LUCID_CONFIG_PATH`, `get_lucid_settings`, class-level `Exp.config`, recruiter,
  locale, wage, and `publish_experiment`.
- `Parameter review notes`: explain which Cint parameters likely need
  experimenter review, especially timeouts, `bid_incidence`, locale, language
  tag, country tag, and per-target wage.
- `Deployment targets`: language-country pairs, PsyNet locale, Lucid tags,
  whether they were verified with `psynet lucid locale`, and any provisional
  source used when API access was unavailable. Include an empty `wage_per_hour`
  column when wages have not been supplied.
- `Deployment CSV`: path, rows added, and any blank wage values requiring human
  review.
- `Qualification tooling`: script path, enabled target tuples, enabled filters,
  and whether real generation was attempted.
- `Lucid API access`: available, missing, unusable, or not checked. Never include
  secret values.
- `Qualification files`: real files generated and temporary placeholder JSON
  files created, with placeholders clearly marked as needing regeneration.
- `Translation files`: per-target `.po` status, warnings for missing files, and
  the exact `psynet translate ...` command needed to create them later.
- `Validation run`: commands run and whether they passed.
- `What the experimenter needs to know`: concise explanations of locale, Lucid
  tags, wage, qualification files, selected filters, API access, and timing/
  incidence parameters.
- `Remaining decisions/blockers`: targets, filters, locale files, wages, Lucid
  credentials, or anything else needed before deployment.
- `Local generation reminder`: state that `create_qualifications.py` has been
  prepared according to the requested targets/filters, but the experimenter must
  run it in their own local repo terminal with valid Lucid API credentials to
  generate real JSON files.
- `Final deployment warning`: emphasize the exact steps the experimenter must
  complete after this agent pass: run `psynet lucid locale` with API access and
  compare tags against `cint_deployment_targets.csv` because locally derived
  tags can be wrong; inspect `create_qualifications.py` before running it because
  it controls Cint screening filters and target JSON files; confirm all target
  `.po` files exist and have been reviewed because `locale` controls the
  participant language; fill `wage_per_hour` for every row because wages are
  country-specific; then, before each deployment, update `locale`, `LANGUAGE`,
  `COUNTRY`, and `wage_per_hour` from `cint_deployment_targets.csv`, either
  manually or with an AI assistant.
- `Readiness status`: one of `target-ready`, `parameter-ready only`, or
  `blocked`.

In the final chat response, repeat the `Final deployment warning` steps in
plain language even if they are already in `CINT_READINESS_REPORT.md`, so the
experimenter sees the next actions without opening the report.

### Example report shape

```text
Cint Readiness Report

Experiment parameters
- COMPLETE: Added get_lucid_settings import.
- COMPLETE: Added LANGUAGE, COUNTRY, and computed LUCID_CONFIG_PATH.
- COMPLETE: Added class-level Exp.config with recruiter, locale,
  recruiter_settings, wage_per_hour, and publish_experiment.
- REVIEW: LANGUAGE/COUNTRY/locale/wage_per_hour must be updated for each real
  deployment target.
- REVIEW: LUCID_CONFIG_PATH is computed as
  f"qualifications/lucid/lucid-{LANGUAGE}-{COUNTRY}.json"; if this file was
  copied from the example JSON, regenerate it before deployment.
- REVIEW: Before each deployment, re-check LANGUAGE, COUNTRY, locale,
  the generated qualification file selected by LUCID_CONFIG_PATH, and
  wage_per_hour against that target's row in cint_deployment_targets.csv.

Deployment targets
| Language | Country | PsyNet locale | Lucid language tag | Lucid country tag | wage_per_hour |
| Turkish  | Turkey  | tr            | TUR                | TR                |               |
| French   | France  | fr            | FRE                | FR                |               |

Deployment CSV
- COMPLETE: Created cint_deployment_targets.csv with locale, language, country,
  language_tag, country_tag, wage_per_hour, and qualification_file columns.
- REVIEW: wage_per_hour is blank for each target and must be filled before
  deployment.

Qualification tooling
- COMPLETE: Created create_qualifications.py.
- COMPLETE: Enabled country_language_tags = (("TUR", "TR"), ("FRE", "FR")).
- COMPLETE: Enabled requested filters: IS_NATIVE V1, HAS_AUDIO v1.
- BLOCKED: Real qualification JSON generation requires local Lucid API access.

Qualification files
- COMPLETE: Added qualifications/lucid/lucid-ENG-GB.json from the example JSON
  shape so the experiment can import structurally.
- REVIEW: This JSON must be regenerated with create_qualifications.py and valid
  Lucid API access before real deployment.
- BLOCKED: Real lucid-TUR-TR.json and lucid-FRE-FR.json must be generated by the
  experimenter in their local repo terminal after Lucid credentials are
  configured.

Parameter review notes
- REVIEW: termination_time_in_s, initial_response_within_s,
  inactivity_timeout_in_s, no_focus_timeout_in_s, and bid_incidence are
  study-specific.
- REVIEW: locale, LANGUAGE, COUNTRY, wage_per_hour, and the generated
  qualification file selected by LUCID_CONFIG_PATH must match each deployment
  target.

What the experimenter needs to know
- locale controls the participant language and must match an existing .po file.
  If a target .po file is missing, Cint scaffolding can still proceed, but the
  experimenter must run psynet translate for that locale and review the
  translation before deployment.
- LANGUAGE and COUNTRY are Lucid market tags; the computed LUCID_CONFIG_PATH
  uses them to select the lucid-<LANGUAGE>-<COUNTRY>.json filename. Run
  psynet lucid locale with Lucid API access to verify market pairs; locally
  derived tags are only provisional until that check or real JSON generation
  succeeds.
- wage_per_hour is country-specific and should be filled separately for every
  row in cint_deployment_targets.csv.
- create_qualifications.py is ready, but real qualification JSON generation
  requires valid Lucid API credentials in the local/deployment environment.
- TIMEOUT is added automatically. Optional filters such as IS_NATIVE,
  BORN_IN_COUNTRY, HAS_AUDIO, and MONOLINGUALISM should be chosen intentionally
  because each one can reduce the qualifying participant pool.
- termination_time_in_s, inactivity_timeout_in_s, no_focus_timeout_in_s, and
  bid_incidence are study-specific review parameters, not universal defaults.

Next local command for the experimenter
- After configuring Lucid API keys locally, run: python create_qualifications.py
- This command is what creates the real qualification JSON files; the agent only
  prepares the script and placeholder structure unless API access is available.

Final deployment warning
- Run psynet lucid locale in an environment with Lucid API access, then compare
  the returned language/country tags against cint_deployment_targets.csv. This
  is needed because locally derived Lucid tags are provisional and a wrong tag
  can target the wrong market or fail qualification generation.
- Inspect create_qualifications.py, then run python create_qualifications.py
  after confirming the tags. This creates the real qualification JSON files that
  Cint/Lucid uses for targeting and screening.
- Confirm all target languages have reviewed locale files. If files are missing,
  run the reported psynet translate command and review the generated .po files;
  otherwise participants may see the wrong language or untranslated text.
- Fill wage_per_hour separately for every target country in
  cint_deployment_targets.csv. This should come from an approved wage or
  minimum-wage source and should not be reused blindly across countries.
- For each deployment, update locale, LANGUAGE, COUNTRY, and wage_per_hour to
  match the selected row, either manually from the table or with help from an AI
  assistant. These values decide the experiment language, Cint target market, and
  payment rate for that deployment.

Readiness status
- parameter-ready only
```

## Rules

- Preserve existing experiment logic and deployment notes.
- Do not configure, inspect, print, or commit real AWS, Cint, Lucid, Prolific, or
  other production credentials.
- Do not use custom or real service credentials for local readiness work unless
  the user explicitly provides a safe deployment workflow.
- Do not claim a copied placeholder Lucid JSON is a real generated
  qualification file. It must be documented as needing regeneration before
  deployment.
- Do not treat missing locales, wages, or qualification decisions as optional;
  report them as blockers for target-specific Cint deployment readiness.
