---
name: upgrade-to-psynet-14
description: Migrates an existing PsyNet experiment through PsyNet 14 breaking changes (in-place timeline defaults, fragment templates, managed page JavaScript, psynet.var, JsPsych module timelines).
---

# Upgrade to PsyNet 14

Use this skill when an experiment needs to move onto PsyNet 14, or when PsyNet
raises an in-place timeline / page JavaScript contract error.

Follow the human checklist in
``docs/whats_new/upgrading_to_psynet_14.rst`` (same steps as below).

Also useful:

- ``docs/whats_new/psynet_14.rst`` — short release highlights
- ``docs/tutorials/writing_custom_frontends.rst`` — authoring patterns
- ``docs/developer/page_lifecycle.rst`` — maintainer lifecycle detail

Do **not** use this skill for greenfield custom pages; point new authors at
the writing-custom-frontends tutorial instead.

## 0. Orient and choose a migration mode

1. Read ``docs/whats_new/upgrading_to_psynet_14.rst``.
2. Run under default ``inplace_timeline_transitions = true``.
3. If temporarily blocked, set ``inplace_timeline_transitions = false`` only as
   a short-term opt-out, then keep migrating pages.

Work page by page. Prefer fixing contract errors over keeping the global
opt-out.

To surface SPA errors quickly, instantiate the page and call
``page._check_spa_template_contract(inplace_timeline_transitions=True)``, or
run ``psynet debug local`` / ``psynet test local`` and read the traceback.

## 1. Find and migrate custom page templates

Search for:

- ``template_path=``
- ``template_str=``
- ``{% extends "timeline-page.html" %}``
- ``template_fragment_path=`` / ``template_fragment_str=`` (already migrated)

Replace complete templates with fragments:

```python
class MyPage(Page):
    def __init__(self):
        super().__init__(
            label="my_page",
            template_fragment_path="templates/my-page.html",
            css_links=["/static/my-page.css"],
            js_page_modules=["/static/my-page.js"],
            time_estimate=5,
        )
```

Fragment HTML rules:

- include only former ``{% block main_body %}`` contents;
- do not include ``{% extends %}``, ``{% block %}``, ``<html>``, ``<head>``, or
  ``<body>``;
- do not embed ``<script>``, ``<style>``, or stylesheet ``<link>`` tags.

## 2. Migrate CSS

Search author-owned templates for ``<style>`` and
``<link rel="stylesheet"``.

- Stylesheet links → ``css_links`` / ``get_css_links()``
- Authored/reusable ``<style>`` blocks → move into ``static/*.css`` and link
  with ``css_links`` / ``get_css_links()``
- Tiny generated snippets → ``css`` / ``get_css()``

## 3. Find deprecated page JavaScript APIs

Search for:

- ``js_links=``
- ``scripts=``
- ``<script>`` tags in author-owned templates or component
  ``external_template`` files

Classify each file before changing it. Remove deprecated arguments once
migrated.

## 4. Migrate a load-once library

Use ``js_dependencies`` / ``get_js_dependencies()`` for classic libraries whose
top-level code should run once per browser document.

```python
Page(..., js_dependencies=["/static/vendor/chart.js"])
```

Do not put page initialization in a dependency.

## 5. Migrate per-page behavior

Classic top-level scripts must be **rewritten** as ES modules that export
``activate``. Do not leave top-level DOM side effects in a file and only change
the Page argument.

Before (classic):

```javascript
document.querySelector("#my-button").addEventListener("click", ...);
```

After (page module):

```javascript
export async function activate({root, trial, vars, page, psynet}) {
    const button = root.querySelector("#my-button");
    button.addEventListener("click", () => {
        psynet.response.staged.rawAnswer = vars["my_config"].answer;
    });
}
```

Wire with ``js_page_modules`` / ``get_js_page_modules()``.

PsyNet imports the module once and calls ``activate()`` for every hosting page.
Most modules need no cleanup: PsyNet removes the page DOM and trial-owned
timers/handlers automatically.

## 6. Migrate inline ``scripts``

Short inline JavaScript → ``js_page_code`` / ``get_js_page_code()`` (runs as an
async activation body with ``root``, ``trial``, ``vars``, ``page``, ``psynet``).

Substantial/reusable code → a ``js_page_modules`` file instead.
Move generated values into ``js_vars`` / ``get_js_vars()`` and read ``vars``.

## 7. Migrate page variables to ``psynet.var``

```javascript
const value = psynet.var.my_variable;
```

Optionally set ``legacy_js_var_globals = error`` while testing. Do not use
``typeof legacy_name`` in ``error`` mode; test with ``"name" in psynet.var``.

## 8. Migrate ``JsPsychPage`` timeline templates

Pass a module URL exporting ``buildTimeline(context)``:

```python
JsPsychPage(..., timeline="/static/my-jspsych-timeline.js")
```

```javascript
export function buildTimeline({jsPsych, vars}) {
    return [{ type: jsPsychHtmlKeyboardResponse, stimulus: vars["welcome_message"] }];
}
```

See ``demos/experiments/jspsych``.

## 9. Choose cleanup deliberately

For resources that survive DOM removal (``window``/``document`` listeners, raw
timers, sockets, observers, object URLs):

- **Preferred for page modules:** return cleanup from ``activate()``
- **Also fine:** ``psynet.addPageEventListener`` /
  ``psynet.addPageCleanupCallback``

```javascript
export function activate({root}) {
    function updateWidth() {
        root.querySelector("#width").textContent = window.innerWidth;
    }
    window.addEventListener("resize", updateWidth);
    updateWidth();
    return function cleanup() {
        window.removeEventListener("resize", updateWidth);
    };
}
```

## 10. Fix timing that assumed document load

- **Page setup** → ``activate()`` / ``js_page_code`` (not ``DOMContentLoaded``)
- **Timing gates** (auto-advance, wait-until-ready) → ``pageReady`` /
  ``trialConstruct``

```javascript
trial.onEvent("pageReady", () => {
    // safe to auto-advance or enable delayed actions
});
```

## 11. Validate the migration

From a complete experiment directory (``experiment.py``, ``test.py``, and
usually ``constraints.txt`` / ``.gitignore``):

```bash
psynet test local
```

Optional PsyNet-repository Playwright only when you already maintain specs
here (harness-specific):

```bash
npx playwright test <relevant-spec>
inplace_timeline_transitions=false npx playwright test <relevant-spec>
```

Check that the default in-place mode works (opt-out removed if possible),
modules activate without console errors, and cleanup runs for persistent
listeners.
