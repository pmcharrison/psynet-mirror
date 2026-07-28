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
2. If one page is temporarily blocked, pass
   ``requires_full_page_reload=True`` to that page's constructor.
3. If many pages are blocked, set ``inplace_timeline_transitions = false``
   only as a short-term experiment-wide opt-out, then keep migrating so you
   can remove it.
4. Work page by page.

To surface SPA contract errors, run ``psynet debug local`` /
``psynet test local`` and read the traceback. Incompatible pages raise one
short message that lists **error codes** in parentheses; use the glossary
below to map each code to a checklist step.

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

Converting the HTML template alone is not enough: leftover ``scripts=`` /
``js_links=`` still force a full-page reload and raise ``legacy_scripts`` /
``legacy_js_links`` unless you also pass ``requires_full_page_reload=True``.

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

From a complete experiment directory. At minimum you typically need:

* ``experiment.py``, ``test.py``, ``constraints.txt``
* ``config.txt``, ``requirements.txt``
* ``.gitignore`` (must include ``source_code.zip``) and ``.python-version``

If you are scaffolding from scratch, see
:doc:`/tutorials/creating_a_new_experiment` or run ``psynet update-scripts``
to generate the standard support files.

.. code-block:: console

    psynet test local

``psynet test local`` checks static timeline pages for SPA contract problems
before bots run, so migration errors should appear directly in the pytest
failure. PageMaker-created pages are still checked when first rendered.

Confirm the default in-place mode works (opt-out removed if possible), page
modules activate without console errors, and cleanup runs for persistent
listeners.

PsyNet-repository Playwright coverage is optional and harness-specific.

Error codes
-----------

SPA incompatibility messages list codes such as
``(error codes: complete_template, style_tag)``. Use them to jump to the
relevant step:

* ``complete_template`` → step 1
* ``style_tag``, ``stylesheet_link`` → step 2
* ``embedded_script`` → steps 3–5
* ``legacy_js_links``, ``legacy_scripts`` → steps 3–5 (also force a reload;
  pass ``requires_full_page_reload=True`` to silence while migrating)
* ``embedded_module`` → step 5 (use ``js_page_modules``, not
  ``<script type="module">`` in HTML)
* ``dom_content_loaded``, ``window_listener_no_cleanup`` → steps 5 and 8
* ``jspsych_html_timeline`` → step 7
