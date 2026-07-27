---
name: upgrade-to-psynet-14
description: Migrates an existing PsyNet experiment through PsyNet 14 breaking changes (in-place timeline defaults, fragment templates, managed page JavaScript, psynet.var, JsPsych module timelines).
---

# Upgrade to PsyNet 14

Use this skill when an experiment needs to move onto PsyNet 14, or when PsyNet
raises an in-place timeline / page JavaScript contract error.

User-facing summary of what changed:
``docs/whats_new/psynet_14.rst``.
Frontend patterns:
``docs/tutorials/writing_custom_frontends.rst``.
Maintainer lifecycle detail:
``docs/developer/page_lifecycle.rst``.

## 0. Orient and choose a migration mode

1. Read ``docs/whats_new/psynet_14.rst``.
2. Run the experiment under the default
   ``inplace_timeline_transitions = true`` configuration.
3. If the author is temporarily blocked, set
   ``inplace_timeline_transitions = false`` only as a short-term opt-out, then
   continue migrating pages so the opt-out can be removed.

Work page by page. Prefer fixing contract errors over keeping the global
opt-out.

## 1. Migrate custom page templates

Search for custom ``Page`` subclasses or ``Page(...)`` calls that still use a
complete template extending ``timeline-page.html``.

Replace with a fragment template:

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

Also fix author-owned template patterns PsyNet rejects under the default:

- ``DOMContentLoaded`` listeners → page module ``activate()`` or trial events;
- ``window.addEventListener(...)`` without cleanup →
  ``psynet.addPageEventListener`` / returned module cleanup /
  ``psynet.addPageCleanupCallback``;
- raw template scripts/styles → managed page asset arguments.

## 2. Find deprecated page JavaScript APIs

Search the experiment for:

- ``js_links=``
- ``scripts=``
- JavaScript ``<script>`` tags in author-owned page templates or component
  ``external_template`` files

Classify each JavaScript file by lifecycle before changing it.
Remove deprecated arguments once their contents have moved to the appropriate
explicit lifecycle.

## 3. Migrate a load-once library

Use ``js_dependencies`` for libraries whose top-level code should run once per
browser document. Dependencies are loaded as classic ``<script src>`` files;
ES modules with page behavior belong in ``js_page_modules`` instead.

```python
Page(
    ...,
    js_dependencies=["/static/vendor/chart.js"],
)
```

For new modular-component code:

```python
def get_js_dependencies(self):
    return ["/static/vendor/chart.js"]
```

Do not put page initialization in a dependency. PsyNet does not rerun dependency
top-level code when another page uses the same URL.

## 4. Migrate per-page behavior

Replace ``js_links`` with ``js_page_modules`` when the file initializes controls,
registers trial handlers, opens sockets, starts timers, or otherwise acts on each
page:

```python
Page(
    ...,
    js_page_modules=["/static/my-page.js"],
)
```

For new modular-component code:

```python
def get_js_page_modules(self):
    return ["/static/my-control.js"]
```

The JavaScript file must be an ES module with a named ``activate`` export:

```javascript
export async function activate({root, trial, vars, page, psynet}) {
    const button = root.querySelector("#my-button");

    function handleClick() {
        psynet.response.staged.rawAnswer = vars["my_config"].answer;
    }

    button.addEventListener("click", handleClick);
}
```

Do not embed a ``<script type="module">`` tag, whether inline or linked with
``src``. PsyNet reserves ES modules for ``js_page_modules``; use standard
``import`` statements from that page module for further dependencies.

PsyNet imports the file once and calls ``activate()`` for every hosting page.
Most page modules do not need to return cleanup: PsyNet removes the page DOM,
stops trial-owned timers and handlers, and resets page response state.

## 5. Migrate inline ``scripts``

Move short inline JavaScript to ``js_page_code``. PsyNet executes it as the body
of an asynchronous activation function with ``root``, ``trial``, ``vars``,
``page``, and ``psynet`` in scope:

Before:

```python
Page(
    ...,
    scripts=[f"window.setup({json.dumps(config)});"],
)
```

After:

```python
Page(
    ...,
    js_vars={"my_config": config},
    js_page_code="window.setup(vars['my_config']);",
)
```

For substantial or reusable code, move the code into a static
``js_page_modules`` file instead. Move Python- or Jinja-generated values into
``js_vars`` or ``get_js_vars()`` and read them from ``vars`` inside
``activate()``.

## 6. Migrate page variables to ``psynet.var``

Replace legacy ``window`` reads of ``js_vars`` keys with ``psynet.var``:

```javascript
const value = psynet.var.my_variable;
```

Optionally set ``legacy_js_var_globals = error`` while testing to find remaining
global reads. Do not use ``typeof legacy_name`` in ``error`` mode; test with
``"name" in psynet.var``.

## 7. Migrate ``JsPsychPage`` timeline templates

``JsPsychPage`` now accepts a JavaScript module URL rather than an HTML/Jinja
timeline template:

```python
JsPsychPage(
    ...,
    timeline="/static/my-jspsych-timeline.js",
)
```

The module must export ``buildTimeline(context)`` and return the timeline array:

```javascript
export function buildTimeline({jsPsych, vars}) {
    return [
        {
            type: jsPsychHtmlKeyboardResponse,
            stimulus: vars["welcome_message"],
        },
    ];
}
```

Move code from the old template's ``{% block timeline %}`` into this function,
replace ``psynet.var`` reads with ``vars``, and remove the old HTML template.
See ``demos/experiments/jspsych``.

## 8. Choose cleanup deliberately

Return cleanup only when ``activate()`` creates resources outside PsyNet's
normal page teardown, such as:

- event listeners on persistent targets such as ``window`` or ``document``
- raw timers not created through the trial
- WebSockets
- observers
- object URLs
- other resources that can survive removal of the page DOM

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

Cleanup functions run in reverse activation order and may be asynchronous.

## 9. Fix timing that assumed document load

Replace ``DOMContentLoaded``-based page setup with trial events such as
``pageReady`` or ``trialConstruct``. Gate custom auto-advance timers on
``pageReady``.

## 10. Validate the migration

```bash
psynet test local
```

When the experiment has browser coverage in this repository:

```bash
npx playwright test <relevant-spec>
inplace_timeline_transitions=false npx playwright test <relevant-spec>
```

For ordinary experiment testing, set
``inplace_timeline_transitions = false`` temporarily in ``config.txt`` only if
needed. The environment-variable form above is for PsyNet's repository
Playwright harness.

Check that:

- the experiment runs with the default in-place mode (opt-out removed if
  possible);
- dependencies load before page behavior;
- repeated pages activate fresh behavior without reloading dependencies;
- leaving a page runs cleanup exactly once;
- the browser console contains no module import or missing ``activate`` errors.
