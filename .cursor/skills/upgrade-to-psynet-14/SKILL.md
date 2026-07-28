---
name: upgrade-to-psynet-14
description: Migrates an existing PsyNet experiment through PsyNet 14 breaking changes by following the human upgrade checklist in docs/whats_new/upgrading_to_psynet_14.rst.
---

# Upgrade to PsyNet 14

Use this skill when an experiment needs to move onto PsyNet 14, or when PsyNet
raises an in-place timeline / page JavaScript contract error.

**Do not use this skill for greenfield custom pages.** Point new authors at
``docs/tutorials/writing_custom_frontends.rst`` instead.

## Source of truth

Read and follow the full checklist in:

``docs/whats_new/upgrading_to_psynet_14.rst``

That page is the single migration procedure for humans and agents. Keep this
skill thin; put checklist edits there, not here.

Related reading (not a second checklist):

- ``docs/whats_new/psynet_14.rst`` — short release highlights
- ``docs/tutorials/writing_custom_frontends.rst`` — authoring patterns
- ``docs/developer/page_lifecycle.rst`` — maintainer lifecycle detail
- ``docs/experiment_development/configuration.rst`` —
  ``inplace_timeline_transitions``, ``legacy_js_var_globals``

## Agent notes

- Search the experiment with the patterns listed in the checklist
  (``template_path=``, ``extends "timeline-page.html"``, ``js_links=``,
  ``scripts=``, embedded ``<script>`` / ``<style>``, and so on).
- Prefer fixing SPA contract errors page by page over leaving
  ``inplace_timeline_transitions = false`` indefinitely.
- To surface contract errors quickly, instantiate the page and call
  ``page._check_spa_template_contract(inplace_timeline_transitions=True)``, or
  run ``psynet debug local`` / ``psynet test local`` and read the traceback.
- ``psynet test local`` needs a complete experiment directory (``experiment.py``,
  ``test.py``, and usually ``constraints.txt``).
- PsyNet-repository Playwright commands in the checklist are optional and
  harness-specific; use them only when you already maintain specs in this repo.
