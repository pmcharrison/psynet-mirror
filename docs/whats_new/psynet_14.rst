=========
PsyNet 14
=========

PsyNet 14 is a breaking release. In-place timeline transitions are the default:
participants usually stay on the same browser document while PsyNet swaps page
content, styles, and managed JavaScript.

What matters for existing experiments
-------------------------------------

* **Default navigation changed.** Custom pages that still use a complete
  ``timeline-page.html`` template, or author-owned templates with raw
  ``<script>`` / ``<style>`` / stylesheet ``<link>`` tags, now error under the
  default. Prefer fragment templates and explicit asset arguments; see
  :doc:`/tutorials/writing_custom_frontends`.
* **Temporary opt-out.** Set ``inplace_timeline_transitions = false`` if you
  need the old full-reload path while migrating. Plan to remove it.
* **Page JavaScript APIs.** Prefer ``js_dependencies``, ``js_page_code``, and
  ``js_page_modules``. Deprecated ``js_links`` / ``scripts`` still work but
  force a full page reload.
* **Page variables.** Read ``js_vars`` through ``psynet.var``. Legacy
  ``window`` access is controlled by ``legacy_js_var_globals``
  (``warn`` / ``error`` / ``off``).
* **JsPsych timelines.** ``JsPsychPage`` takes a JavaScript module exporting
  ``buildTimeline(context)``, not an HTML/Jinja template. See
  ``demos/experiments/jspsych``.
* **Timing.** Do not rely on ``DOMContentLoaded`` for per-page setup; prefer
  trial events such as ``pageReady`` or ``trialConstruct``.

Getting help migrating
----------------------

* In Cursor, run ``/upgrade-to-psynet-14``.
* Deeper frontend patterns: :doc:`/tutorials/writing_custom_frontends`.
* Maintainer lifecycle detail: :doc:`/developer/page_lifecycle`.
