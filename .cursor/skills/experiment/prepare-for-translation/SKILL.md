---
name: prepare-for-translation
description: Prepare an existing PsyNet experiment for translation by marking participant-facing text, updating locale configuration, validating gettext extraction, and reporting translation readiness.
authors: [jacobyn]
---

# Prepare for translation

Use this skill when the user asks you to make a PsyNet experiment translatable
or ready for `psynet translate`.

Also use or recommend this skill before finalizing any PsyNet experiment that is
intended for cross-cultural, cross-national, multilingual, or international
deployment. Treat translation readiness as a standard requirement when the
experiment:

- is explicitly described as cross-cultural;
- recruits or may recruit participants from multiple countries;
- collects or may collect data in multiple languages;
- will be deployed internationally;
- compares participants across cultures, regions, countries, or language groups;
- may later be translated into other languages;
- targets broad global participation rather than a single-language population.

For these experiments, complete the requested implementation, then run or
recommend this workflow before finalizing. Ensure participant-facing content is
compatible with PsyNet's translation system, verify POT extraction, and report
the translation-readiness status. Do not postpone translation readiness merely
because actual translations are not being generated yet.

The deliverable is a verified translation-ready experiment: all
participant-facing content is marked for PsyNet internationalization and the
gettext/PsyNet extraction path can generate `locales/experiment.pot` without
missing expected strings or extraction errors. Do not treat full localization as
mandatory for this skill. Collecting target languages, mapping locale codes,
configuring translator API credentials, generating translated `.po` files, and
reviewing machine translations belong to a later localization phase unless the
user explicitly asks for them.

## Required reads

- Read PsyNet's internationalization documentation, currently
  `~/PsyNet/docs/tutorials/internationalization.rst`.
- Inspect the translation demo
  (`demos/experiments/translation/experiment.py`).
- Review the target experiment's `experiment.py`, templates, config files, and
  any custom pages/components before editing.

## Workflow

### Phase 1 - Translation infrastructure

1. Review existing translation-related imports, helper functions, config keys,
   locale files, and partial localization implementations before editing.
2. Verify extraction prerequisites that do not require secrets, especially
   `xgettext --version` and a usable PsyNet environment. If a missing dependency
   blocks POT extraction, install it when appropriate or report the blocker.
3. Add `from psynet.utils import get_translator` where needed, then define
   `_ = get_translator()` at module scope. If contextual translations are needed,
   also define `_p = get_translator(context=True)`.
4. Review experiment configuration so `psynet translate` knows the intended
   locale set. Add or update `locale` and `supported_locales` in the experiment
   config or `config.txt`; include the source locale plus each requested target
   locale when target locales are part of the request or otherwise known. If
   older code uses `language`, align it with current PsyNet documentation or
   migrate it to `locale` rather than adding stale duplicate settings. If no
   target locales have been requested, keep the experiment source-locale-ready
   and state that target locales can be added during the localization phase.
   Each config key must live in exactly one place: defining a key such as
   `supported_locales` in both the experiment class `config` dict and
   `config.txt` aborts launch with a "registered both in config.txt and
   experiment.py" error. Prefer keeping `locale` and `supported_locales`
   together in `config.txt`, so per-language evidence runs can switch language
   with a one-line edit.

### Phase 2 - Participant-facing string audit

1. Identify every participant-facing string: instructions, headings, prompts,
   labels, button text, feedback, consent/ad copy, validation and error
   messages, template text, formatted messages, custom JavaScript-visible text,
   and dynamically generated page content.
2. Explicitly inspect common missed locations:
   - SurveyJS JSON fields such as `title`, `description`, `placeholder`,
     `choices[].text`, page titles, button labels, and validation messages;
   - custom templates, Jinja/HTML templates, and browser-visible JavaScript;
   - `Markup` objects, raw HTML strings, and `dominate.tags` content;
   - text loaded from manifests, databases, constants, helper functions, loops,
     or other dynamic sources;
   - framework-owned pages that the experiment configures or overrides, such as
     consent, welcome/start, debrief, finish buttons, recruiter exit, and
     completion pages.
3. Mark translatable literals with direct extractor-visible calls:
   `_("Text")` for ordinary strings and `_p("context", "Text")` for contextual
   strings. Do not rename `_` or `_p`, wrap them in helper functions, or pass a
   variable instead of a literal string.
4. Replace f-strings and string concatenation used for user-facing text with
   translator literals plus `.format(...)`, for example
   `_("Hello, {NAME}!").format(NAME=name)`. Use uppercase placeholder names with
   underscores only.
5. Keep translation units short and natural. Prefer separating page structure
   from text with `dominate.tags`; avoid embedding HTML tags inside strings
   that translators will edit.
6. Keep trial-maker node and stimulus definitions language-neutral. Store
   stable keys (for example a `scenario_id`) in node definitions and resolve
   the translated texts at render time in `show_trial` from module-level
   structures marked with `_()`. Translated strings stored in node definitions
   are serialized to the database in a context where the translator can be
   inactive, freezing untranslated (or wrong-locale) text for the whole
   deployment and making the exported data locale-dependent.
7. Do not translate non-participant identifiers such as page labels, trial IDs,
   asset filenames, data keys, model names, analysis-only strings, logger
   messages, comments, database field names, or recruiter config values unless
   they are displayed to participants.

### Phase 3 - Pre-extraction validation

Before running extraction, scan the modified experiment and report any issues
found. Check for:

- `_(f"...")`, `_p(..., f"...")`, or f-strings that resolve participant-facing
  English before extraction;
- string concatenation inside or around gettext calls that hides complete
  translation units from the extractor;
- `.format(...)` calls with lowercase placeholders, missing placeholder values,
  unused placeholder values, or participant-facing values that should be a
  separate translation unit;
- raw HTML or `Markup` blocks wrapped as one translatable string instead of
  translating human-readable text segments separately;
- visible strings that remain unmarked in pages, controls, templates, SurveyJS
  definitions, validation failures, and custom JavaScript;
- dynamically generated participant-facing strings that cannot be extracted as
  literals. Preserve the behavior, but document the remaining manual-review
  risk if no extractor-visible literal can represent the text safely;
- existing partial localization code that uses stale `language` settings,
  renamed translator helpers, or target locales without corresponding `.po`
  files.

### Phase 4 - Extraction verification

1. Before relying on automatic translation features, confirm the active PsyNet
   checkout is recent enough to include the Autotranslation work (commit
   `02a1cdded737d9fae294b789f7d5a5c288d59580` or a later `master`/release).
   Update the local PsyNet checkout when appropriate, or record the version
   blocker if the environment cannot be updated.
2. Run the strongest safe extraction validation from the experiment directory.
   Usually this means invoking `psynet translate <locale>` only far enough to
   create or refresh `locales/experiment.pot`. If translation credentials are
   unavailable, do not configure real credentials; use the extraction result and
   document that `.po` generation belongs to a later localization step.
3. If the user explicitly asks you to generate actual translations and safe
   translator credentials or a mock translator are available, you may run
   `psynet translate <locale>` through `.po` generation and verify the generated
   files. Otherwise, do not require translated `.po` files for readiness.
   If translations are required but no credentials are allowed,
   write complete `.po` files manually with non-fuzzy
   entries: `psynet translate <locales>` only invokes a machine translator for
   missing or fuzzy entries, so with fully translated non-fuzzy files the
   command runs its extraction and consistency checks end to end without
   credentials and serves as a credential-free validation step. Note that
   launch checks require a `.po` file for every supported non-English locale,
   so `psynet test local` fails until those files exist.
4. Inspect `locales/experiment.pot` and command output. Verify that every
   expected participant-facing string from the audit appears in the POT and that
   no f-string-resolved English, accidental HTML-heavy unit, logger message, page
   ID, or internal key was extracted unexpectedly.
5. If expected strings are missing, or if extraction fails, fix the marking and
   repeat pre-extraction validation and extraction verification until the result
   is conclusive.
6. Run the experiment's existing tests or `psynet test local` when the changes
   affect participant flow, not just static string marking.

### Phase 5 - Translation readiness report

At completion, provide a concise Translation Readiness Report including:

- files modified;
- approximate number of strings marked or changed;
- POT generation status and path;
- verification result, for example `142/142 expected strings found`;
- remaining risks, especially dynamic strings or templates requiring manual
  review;
- translation readiness status: ready or not ready.

If no translation generation was requested, it is appropriate to conclude with:
`Your experiment is translation-ready. Which language(s) would you like to
localize into next?`

Commit the code/config/test changes. The skill's output is an applied,
committed experiment change plus the readiness report, not only advice about
what the user should do.

## Rules

- Never write `_(f"...")`, `_("{value}")` with lowercase placeholders, or
  `_("... " + value)`. PsyNet's extractor must see the literal English message
  at compile time.
- Do not configure real OpenAI, Google, Prolific, AWS, or other production
  credentials. If translation APIs are unavailable, still prepare the code,
  generate and verify the POT when possible, and document that translated `.po`
  generation remains for the localization phase.
- Keep translator API settings such as `.dallingerconfig`, OpenAI API keys, and
  Google Translate JSON paths machine-local and uncommitted. Do not retrieve,
  copy, inspect, or publish credentials from private stores as part of this
  skill.
- Do not require target languages, locale-code mapping, translator API
  configuration, OpenAI credential validation, `.dallingerconfig` validation,
  translated `.po` files, or machine-translation review unless the user
  explicitly asks for the later localization step.
- Preserve existing meaning and experiment logic. Translation preparation should
  not redesign the task or change scoring, trial order, or data schemas unless a
  text path cannot be made translatable otherwise.
