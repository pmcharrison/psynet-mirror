=========
PsyNet 14
=========

PsyNet 14 makes timeline navigation feel like a modern web app.

Instead of reloading the whole browser page every time a participant moves
on, PsyNet keeps the experiment open and swaps in the next step in place.
That means smoother transitions, less waiting on repeated page loads, and a
better chance of preserving useful browser state — audio, video, and custom
frontends included — as people move through the timeline.

Under the hood this is powered by clearer page lifecycle APIs for templates,
styles, and JavaScript, so custom pages can take part in that fluent
navigation instead of fighting a full reload on every step.

Upgrading
---------

PsyNet 14 is a breaking release for some custom frontends. If you are updating
an existing experiment:

* Start from the author-facing frontend guide:
  :doc:`/tutorials/writing_custom_frontends`.
* In Cursor, run the repo-local ``/upgrade-to-psynet-14`` skill for a
  step-by-step migration.
* If you need the old full-reload behavior temporarily while migrating, set
  ``inplace_timeline_transitions = false``, then remove it once the experiment
  is ready for the default.
