=====================
Upgrading to PsyNet 14
=====================

This checklist migrates an existing experiment onto PsyNet 14's default
in-place timeline transitions. It is written for humans; the Cursor skill
``/upgrade-to-psynet-14`` follows the same steps.

Background: :doc:`/whats_new/psynet_14`. Frontend patterns:
:doc:`/tutorials/writing_custom_frontends`. Config keys:
:doc:`/experiment_development/configuration`.

0. Orient
---------

1. Run under the default ``inplace_timeline_transitions = true``.
2. If you are temporarily blocked, set
   ``inplace_timeline_transitions = false`` only as a short-term opt-out,
   then keep migrating pages so you can remove it.
3. Work page by page. Prefer fixing contract errors over keeping the global
   opt-out.

To surface SPA contract errors without a full browser session, instantiate
the page in a Python shell / test and call
``page._check_spa_template_contract(inplace_timeline_transitions=True)``,
or simply run ``psynet debug local`` / ``psynet test local`` and read the
traceback.

1. Find and migrate custom page templates
-----------------------------------------

Search for:

* ``template_path=``
* ``template_str=``
* ``{% extends "timeline-page.html" %}``

Complete templates that extend ``timeline-page.html`` must become fragments:

.. code-block:: python

    class MyPage(Page):
        def __init__(self):
            super().__init__(
                label="my_page",
                template_fragment_path="templates/my-page.html",
                css_links=["/static/my-page.css"],
                js_page_modules=["/static/my-page.js"],
                time_estimate=5,
            )

Fragment HTML rules:

* include only the former ``{% block main_body %}`` contents;
* do not include ``{% extends %}``, ``{% block %}``, ``<html>``, ``<head>``,
  or ``<body>``;
* do not embed ``<script>``, ``<style>``, or stylesheet ``<link>`` tags.

2. Migrate CSS
--------------

* Template ``<link rel="stylesheet" href="...">`` → ``css_links`` (or
  ``get_css_links()`` on a Prompt/Control).
* Template ``<style>...</style>`` → a ``static/*.css`` file + ``css_links``
  when the styles are authored/reusable; use the ``css`` argument (or
  ``get_css()``) only for tiny generated snippets.

3. Find deprecated page JavaScript APIs
--------------------------------------

Search for:

* ``js_links=``
* ``scripts=``
* ``<script>`` tags in author-owned templates or component
  ``external_template`` files

Classify each script before moving it.

4. Migrate load-once libraries
------------------------------

Use ``js_dependencies`` (or ``get_js_dependencies()``) for classic libraries
whose top-level code should run once per browser document. Do not put
per-page initialization in a dependency.

5. Migrate per-page behavior
----------------------------

Rewrite classic page scripts as ES modules that export ``activate``:

.. code-block:: javascript

    // Before (classic top-level script):
    // document.querySelector("#my-button").addEventListener(...)

    export async function activate({root, trial, vars, page, psynet}) {
        const button = root.querySelector("#my-button");
        button.addEventListener("click", () => {
            psynet.response.staged.rawAnswer = vars["my_config"].answer;
        });
    }

Wire them with ``js_page_modules`` / ``get_js_page_modules()``.

Short inline snippets can use ``js_page_code`` / ``get_js_page_code()``
instead of a module file.

6. Migrate page variables to ``psynet.var``
------------------------------------------

Replace legacy ``window`` reads of ``js_vars`` keys with ``psynet.var``.
Optionally set ``legacy_js_var_globals = error`` while testing.

7. Migrate JsPsych timelines
----------------------------

``JsPsychPage`` takes a JavaScript module URL exporting
``buildTimeline(context)``, not an HTML/Jinja template. See
``demos/experiments/jspsych``.

8. Choose cleanup deliberately
------------------------------

For ``window`` / ``document`` listeners and other resources that survive DOM
removal, either:

* return a cleanup function from ``activate()`` (preferred for page modules),
  or
* use ``psynet.addPageEventListener`` /
  ``psynet.addPageCleanupCallback``.

9. Fix timing that assumed document load
----------------------------------------

* **Page setup** (wire buttons, start widgets): put it in
  ``activate()`` / ``js_page_code``. Do **not** use ``DOMContentLoaded``.
* **Timing gates** (auto-advance, wait-until-ready): use trial events such as
  ``pageReady`` or ``trialConstruct``.

Example timing gate:

.. code-block:: javascript

    trial.onEvent("pageReady", () => {
        // safe to auto-advance or enable delayed actions
    });

10. Validate
------------

From a complete experiment directory (needs ``experiment.py``, ``test.py``,
and usually ``constraints.txt``):

.. code-block:: console

    psynet test local

Confirm the experiment runs with the default in-place mode (opt-out removed
if possible), page modules activate without console errors, and cleanup runs
when leaving pages that attach persistent listeners.

PsyNet repository Playwright coverage is optional and harness-specific; use
it only when you already maintain specs in this repo.
