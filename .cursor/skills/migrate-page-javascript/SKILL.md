---
name: migrate-page-javascript
description: Migrates removed PsyNet js_links, scripts, get_js_links, and get_scripts APIs to js_dependencies and lifecycle-managed js_page_scripts.
---

# Migrate page JavaScript

Use this skill when an experiment fails because PsyNet no longer accepts
``js_links`` or ``scripts``, or when a custom ``Prompt`` or ``Control`` still
implements ``get_js_links()`` or ``get_scripts()``.

## 1. Find the removed API

Search the experiment for:

- ``js_links=``
- ``scripts=``
- ``def get_js_links``
- ``def get_scripts``
- JavaScript ``<script>`` tags in custom page, prompt, or control markup

Classify each JavaScript file by lifecycle before changing it.

## 2. Migrate a load-once library

Use ``js_dependencies`` for libraries whose top-level code should run once per
browser document:

```python
Page(
    ...,
    js_dependencies=["/static/vendor/chart.js"],
)
```

For a modular component:

```python
def get_js_dependencies(self):
    return ["/static/vendor/chart.js"]
```

Do not put page initialization in a dependency. PsyNet does not rerun dependency
top-level code when another page uses the same URL.

## 3. Migrate per-page behavior

Replace ``js_links`` with ``js_page_scripts`` when the file initializes controls,
registers trial handlers, opens sockets, starts timers, or otherwise acts on each
page:

```python
Page(
    ...,
    js_page_scripts=["/static/my-page.js"],
)
```

For a modular component:

```python
def get_js_page_scripts(self):
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

    return async function cleanup() {
        button.removeEventListener("click", handleClick);
    };
}
```

PsyNet imports the file once, calls ``activate()`` for every hosting page, and
calls the returned cleanup function before leaving. Cleanup is optional.

## 4. Migrate inline ``scripts``

Move inline JavaScript into a file under ``static/`` and list that URL in
``js_page_scripts``. Move Python- or Jinja-generated values into ``js_vars`` or
``get_js_vars()`` and read them from ``vars`` inside ``activate()``.

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
    js_page_scripts=["/static/setup-page.js"],
)
```

```javascript
export async function activate({vars}) {
    window.setup(vars["my_config"]);
}
```

## 5. Choose cleanup deliberately

Return cleanup whenever ``activate()`` creates:

- DOM or window event listeners
- timers
- WebSockets
- observers
- object URLs
- other resources that can survive removal of the page DOM

Cleanup functions run in reverse activation order and may be asynchronous.

## 6. Validate the migration

Run focused tests for the experiment, then verify both transition modes when the
experiment supports them:

```bash
psynet test local
npx playwright test <relevant-spec>
inplace_timeline_transitions=false npx playwright test <relevant-spec>
```

Check that:

- dependencies load before page behavior;
- repeated pages activate fresh behavior without reloading dependencies;
- leaving a page runs cleanup exactly once;
- the browser console contains no module import or missing ``activate`` errors.

For more context, see ``docs/tutorials/writing_custom_frontends.rst``, section
“Managing JavaScript lifecycles”.
