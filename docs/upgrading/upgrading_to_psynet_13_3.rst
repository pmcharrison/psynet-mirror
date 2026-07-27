========================
Upgrading to PsyNet 13.3
========================

Introduction
============

PsyNet 13.3 makes **in-place timeline transitions** the default. Participants
usually stay on the same browser document while PsyNet swaps the next page's
markup, styles, and managed JavaScript. That is faster and more stable for
media and custom frontends, but it changes how custom pages must declare
templates and scripts.

This guide covers the migration steps most experiment authors need. For the
full maintainer-level lifecycle model, see
:doc:`/developer/page_lifecycle`. For custom frontend patterns, see
:doc:`/tutorials/writing_custom_frontends`.

If you need the old full-reload behavior while migrating, set the following in
your Experiment configuration (for example in ``config.txt`` or
``Experiment.config``):

.. code-block:: text

    inplace_timeline_transitions = false

That opt-out keeps legacy templates working, but PsyNet may still warn about
patterns that are incompatible with the default in-place mode. Plan to migrate
and remove the opt-out.

In-place timeline transitions
=============================

What changed
____________

Previously, many deployments still used a full page reload for every timeline
step. PsyNet 13.3 defaults to in-place transitions:

* the browser document stays open;
* PsyNet replaces ``#timeline-header``, ``#main-body``, ``#footer``, and
  ``#psynet-template-data``;
* page assets are activated and cleaned up explicitly instead of relying on a
  fresh document load.

Action needed
_____________

1. Run your experiment locally under the default configuration (do **not** set
   ``inplace_timeline_transitions = false`` unless you are temporarily blocked).
2. If PsyNet raises a template or JavaScript contract error for a custom page,
   migrate that page using the sections below.
3. Prefer migrating pages one at a time rather than keeping the global opt-out
   indefinitely.

Custom page templates
=====================

What changed
____________

Custom pages that still use a **complete** template extending
``timeline-page.html`` are incompatible with the default in-place mode unless
PsyNet marks the template as framework-owned. Author-owned templates must
provide only the contents of the ``main_body`` block.

Action needed
_____________

Replace complete custom templates with fragment templates:

.. code-block:: python

    from psynet.timeline import Page


    class MyPage(Page):
        def __init__(self):
            super().__init__(
                label="my_page",
                template_fragment_path="templates/my-page.html",
                css_links=["/static/my-page.css"],
                js_page_modules=["/static/my-page.js"],
                time_estimate=5,
            )

In the fragment HTML file:

* include only the markup that used to live inside ``{% block main_body %}``;
* do **not** include ``{% extends "timeline-page.html" %}``, ``{% block ... %}``,
  ``<html>``, ``<head>``, or ``<body>``;
* do **not** embed ``<script>``, ``<style>``, or stylesheet ``<link>`` tags in
  the author-owned template.

Supply page-local assets through explicit Page arguments instead:

* ``css`` / ``css_links`` for styles;
* ``js_dependencies`` for libraries loaded once per browser document;
* ``js_page_code`` for short inline activation snippets;
* ``js_page_modules`` for per-page module behavior.

PsyNet also rejects common SPA-incompatible patterns in author-owned templates,
including ``DOMContentLoaded`` listeners and ``window`` listeners without
cleanup. See :doc:`/tutorials/writing_custom_frontends` for the full checklist.

Page JavaScript APIs
====================

What changed
____________

The Page arguments ``js_links`` and ``scripts`` are deprecated. They keep classic
linked/inline script semantics and therefore **force a full page reload**
rather than participating in the managed in-place JavaScript path.

Prefer:

* ``js_dependencies`` — classic scripts loaded once per document;
* ``js_page_code`` — short per-page activation bodies;
* ``js_page_modules`` — ES modules that export ``activate(context)`` and may
  return cleanup.

Modular prompts and controls expose the same lifecycles through
``get_js_dependencies()``, ``get_js_page_code()``, and
``get_js_page_modules()``.

Action needed
_____________

1. Search your experiment for ``js_links=``, ``scripts=``, and raw ``<script>``
   tags in author-owned templates.
2. Classify each file:

   * load-once library → ``js_dependencies``;
   * short page setup → ``js_page_code``;
   * substantial or reusable page behavior → ``js_page_modules``.
3. For page modules, export ``activate`` and clean up resources that survive DOM
   teardown (for example ``window`` listeners, sockets, workers, raw timers):

   .. code-block:: javascript

       export function activate({root, trial, vars, page, psynet}) {
           function onResize() {
               /* ... */
           }
           window.addEventListener("resize", onResize);
           return function cleanup() {
               window.removeEventListener("resize", onResize);
           };
       }

In Cursor, run the repo-local ``/migrate-page-javascript`` skill for a
step-by-step conversion of deprecated Page arguments.

Page JavaScript variables
=========================

What changed
____________

Historically, PsyNet copied each ``js_vars`` key onto ``window``. That is
deprecated because in-place transitions reuse the same browser window across
pages. Read page variables through ``psynet.var`` instead:

.. code-block:: javascript

    const value = psynet.var.my_variable;
    // or
    const also = psynet.var["my_variable"];

Compatibility is controlled by ``legacy_js_var_globals``:

* ``warn`` (default) — legacy ``window`` access still works and warns once per
  key;
* ``error`` — legacy access throws an informative ``ReferenceError``;
* ``off`` — PsyNet does not install legacy global properties.

Action needed
_____________

1. Update custom JavaScript to use ``psynet.var``.
2. Optionally set ``legacy_js_var_globals = error`` in local testing to find
   remaining global reads.
3. Do not rely on ``typeof legacy_name`` in ``error`` mode; test availability
   with ``"name" in psynet.var``.

JsPsych timelines
=================

What changed
____________

``JsPsychPage`` no longer accepts HTML/Jinja timeline templates. Pass a
JavaScript module URL that exports ``buildTimeline(context)``:

.. code-block:: python

    JsPsychPage(
        "reaction_time_task",
        timeline="/static/reaction-time-task.js",
        time_estimate=25,
        js_dependencies=[
            "static/jspsych/jspsych.js",
            "static/jspsych/plugin-html-keyboard-response.js",
        ],
        css_links=["static/jspsych/jspsych.css"],
    )

.. code-block:: javascript

    export function buildTimeline({jsPsych, vars, page, psynet, root}) {
        return [
            {
                type: jsPsychHtmlKeyboardResponse,
                stimulus: vars.welcome_message,
                choices: "NO_KEYS",
                trial_duration: 0,
            },
        ];
    }

See ``demos/experiments/jspsych`` for a complete example. ``JsPsychPage`` and
``UnityPage`` also use full document reloads when entering or leaving their
runtimes, so they do not participate in fragment teardown across those
boundaries.

Action needed
_____________

Convert any Jinja/HTML jsPsych timeline templates into modules exporting
``buildTimeline``. The ``/migrate-page-javascript`` skill covers this migration
as well.

Timing and page readiness
=========================

What changed
____________

Under in-place transitions, page setup should not assume ``DOMContentLoaded``.
PsyNet marks the page ready and registers the ``pageReady`` trial event after
managed JavaScript activation. Automatic pages and WaitPage-style timers should
wait for readiness rather than racing document-load events.

Action needed
_____________

* Prefer trial events such as ``pageReady`` or ``trialConstruct`` for setup that
  used to hang off ``DOMContentLoaded``.
* If you schedule auto-advance or other timers from custom page code, gate them
  on ``pageReady``.

Further reading
===============

* :doc:`/tutorials/writing_custom_frontends` — fragment templates and managed
  JavaScript for experiment authors.
* :doc:`/developer/page_lifecycle` — full in-place transition sequence and
  document-owning page policy.
* :doc:`/developer/package_static_resources` — package-owned static URLs for
  reusable components.
* :doc:`/upgrading/upgrading_to_psynet_10` — earlier major-version upgrade guide.
