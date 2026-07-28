=====================
Upgrading to PsyNet 14
=====================

This checklist migrates an existing experiment onto PsyNet 14's default
in-place timeline transitions. It is the single source of truth for
**migration order and search targets**. Frontend patterns and full examples
live in :doc:`/tutorials/writing_custom_frontends`.

The Cursor skill ``/upgrade-to-psynet-14`` is a thin wrapper that points agents
here.

Also see: :doc:`/whats_new/psynet_14`,
:doc:`/experiment_development/configuration`.

0. Orient
---------

1. Run under the default ``inplace_timeline_transitions = true``.
2. If temporarily blocked, set ``inplace_timeline_transitions = false`` only
   as a short-term opt-out, then keep migrating so you can remove it.
3. Work page by page.

To surface SPA contract errors quickly, call
``page._check_spa_template_contract(inplace_timeline_transitions=True)``, or
run ``psynet debug local`` / ``psynet test local`` and read the traceback.

1. Find and migrate custom page templates
-----------------------------------------

Search for ``template_path=``, ``template_str=``, and
``{% extends "timeline-page.html" %}``.

Convert complete templates to fragments
(``template_fragment_path`` / ``template_fragment_str``) and supply assets via
page arguments. See :doc:`/tutorials/writing_custom_frontends`
(Custom page templates).

2. Migrate CSS
--------------

Search author-owned templates for ``<style>`` and
``<link rel="stylesheet">``.

* Stylesheet links → ``css_links`` / ``get_css_links()``
* Authored reusable styles → ``static/*.css`` + ``css_links``
* Tiny generated snippets → ``css`` / ``get_css()``

See the same tutorial section for details.

3. Find deprecated page JavaScript APIs
--------------------------------------

Search for ``js_links=``, ``scripts=``, and ``<script>`` tags in author-owned
templates or component ``external_template`` files. Classify each script
before moving it (load-once library vs per-page behavior vs short inline).

4. Migrate load-once libraries
------------------------------

Move load-once classic libraries to ``js_dependencies`` /
``get_js_dependencies()``. Do not put per-page initialization there. See
:doc:`/tutorials/writing_custom_frontends` (Managing JavaScript lifecycles).

5. Migrate per-page behavior
----------------------------

Rewrite classic top-level scripts as ES modules that export ``activate``,
wired with ``js_page_modules`` / ``get_js_page_modules()``. Short snippets may
use ``js_page_code`` / ``get_js_page_code()`` instead.

See :doc:`/tutorials/writing_custom_frontends` for ``activate(context)``
examples and cleanup guidance.

6. Migrate page variables to ``psynet.var``
------------------------------------------

Replace legacy ``window`` reads of ``js_vars`` keys with ``psynet.var``.
Optionally set ``legacy_js_var_globals = error`` while testing. See
:doc:`/tutorials/writing_custom_frontends` and
:doc:`/experiment_development/configuration`.

7. Migrate JsPsych timelines
----------------------------

``JsPsychPage`` takes a JavaScript module URL exporting
``buildTimeline(context)``, not an HTML/Jinja template. See
``demos/experiments/jspsych``.

8. Fix timing that assumed document load
----------------------------------------

* Page setup → ``activate()`` / ``js_page_code`` (not ``DOMContentLoaded``)
* Timing gates → ``pageReady`` / ``trialConstruct``

Details: :doc:`/tutorials/writing_custom_frontends`.

9. Validate
-----------

From a complete experiment directory (``experiment.py``, ``test.py``, and
usually ``constraints.txt``):

.. code-block:: console

    psynet test local

Confirm the default in-place mode works (opt-out removed if possible), page
modules activate without console errors, and cleanup runs for persistent
listeners.

PsyNet-repository Playwright coverage is optional and harness-specific.
