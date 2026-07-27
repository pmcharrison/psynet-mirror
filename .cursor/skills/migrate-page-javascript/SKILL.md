---
name: migrate-page-javascript
description: Migrates deprecated PsyNet Page js_links and scripts arguments to js_dependencies, js_page_code, and lifecycle-managed js_page_modules.
---

# Migrate page JavaScript

Use this skill when PsyNet warns that an experiment still uses the deprecated
``js_links`` or ``scripts`` arguments.

## 1. Find the removed API

Search the experiment for:

- ``js_links=``
- ``scripts=``
- JavaScript ``<script>`` tags in author-owned page templates or component
  ``external_template`` files

Classify each JavaScript file by lifecycle before changing it.
Remove deprecated arguments once their contents have moved to the appropriate
explicit lifecycle.

## 2. Migrate a load-once library

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

## 3. Migrate per-page behavior

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

## 4. Migrate inline ``scripts``

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

## 5. Migrate ``JsPsychPage`` timeline templates

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
PsyNet detects HTML paths and old Jinja timeline files and reports this
migration directly.

## 6. Choose cleanup deliberately

Return cleanup only when ``activate()`` creates resources outside PsyNet's
normal page teardown, such as:

- event listeners on persistent targets such as ``window`` or ``document``
- raw timers not created through the trial
- WebSockets
- observers
- object URLs
- other resources that can survive removal of the page DOM

For example, a ``window`` listener survives removal of the page DOM and must be
removed explicitly:

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

## 7. Validate the migration

Run focused tests for the experiment, then verify both transition modes when the
experiment supports them:

```bash
psynet test local
npx playwright test <relevant-spec>
inplace_timeline_transitions=false npx playwright test <relevant-spec>
```

For ordinary experiment testing, set
``inplace_timeline_transitions = false`` temporarily in ``config.txt``. The
environment-variable form above is intended for PsyNet's repository Playwright
harness, which passes environment configuration to the test experiment.

Check that:

- dependencies load before page behavior;
- repeated pages activate fresh behavior without reloading dependencies;
- leaving a page runs cleanup exactly once;
- the browser console contains no module import or missing ``activate`` errors.

For more context, see ``docs/upgrading/upgrading_to_psynet_14.rst`` for the
full PsyNet 14 upgrade checklist, and
``docs/tutorials/writing_custom_frontends.rst``, section “Managing JavaScript
lifecycles”.
