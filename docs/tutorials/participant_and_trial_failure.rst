Participant and trial failure
=============================

PsyNet distinguishes participant failure from trial failure. These concepts are
related, but they describe different things:

* A failed **participant** did not successfully complete the experiment.
* A failed **trial** is a retained trial record that should no longer be treated
  as valid experimental data.
* **Failure propagation** determines whether failing one object should also
  invalidate objects that depend on it.

Keeping these concepts separate is important. For example, a participant might
be unable to continue because another member of their synchronous group
disconnected, while the trials they already completed remain perfectly usable.
Conversely, an individual trial might fail during recording analysis without
requiring the participant to be failed.


Trial failure
-------------

Calling :meth:`~psynet.trial.main.Trial.fail` marks a trial as failed and records
its failure reason. Failure is monotonic: PsyNet does not provide a way to make a
failed trial valid again.

Failed trials are not deleted. They remain available in the database and raw
data exports, together with their ``failed`` and ``failed_reason`` fields. Many
PsyNet APIs exclude them from normal experimental operations; for example,
``alive_trials`` means all trials that are not failed, and chain growth uses
non-failed trials when determining whether a node is ready to grow. Analysis
code should explicitly decide whether failed trials should be included and will
normally filter them out.

Trial completion, finalization, and failure are distinct dimensions:

* ``complete`` means that a response was submitted.
* ``finalized`` means that required post-trial processing completed and
  finalization hooks ran.
* ``failed`` means that the trial is no longer considered valid.

A completed or finalized trial can therefore later be failed, for example when
a participant-level performance check invalidates that participant's data.
Failing such a trial does not undo participant progress, scores, or payments
that have already been awarded.


When trials should fail
-----------------------

A trial should be failed when the trial itself is unusable, when an explicit
TrialMaker policy invalidates it following participant failure, or when it
depends on another failed object.

Examples of trial-local failures include:

* a response timeout;
* failed recording analysis or required post-processing;
* a duplicate or structurally inconsistent trial;
* custom experiment logic that determines that a response is unusable.

These cases should normally fail the affected trial, not every trial belonging
to the participant.


Participant failure
-------------------

Calling :meth:`~psynet.participant.Participant.fail` marks the participant as
failed and runs the experiment's registered participant-failure routines. It
does not inherently fail the participant's trials.

Each TrialMaker independently decides whether a participant failure invalidates
the trials belonging to that TrialMaker. This keeps invalidation scoped
correctly in experiments containing multiple TrialMakers with different data
requirements.

PsyNet currently recognizes two participant failure causes for automatic trial
invalidation:

``premature_exit``
    Controlled by ``fail_trials_on_premature_exit``.

``performance_check``
    Controlled by ``fail_trials_on_participant_performance_check``.

If the corresponding option is ``True``, all non-failed trials belonging to
that participant and TrialMaker are failed. This includes completed and
finalized trials. If it is ``False``, those trials are preserved. Participant
failure for any other reason preserves trials unless custom failure logic
explicitly fails them.

The default policies reflect the different data dependencies of each paradigm:

.. list-table::
   :header-rows: 1

   * - TrialMaker
     - Premature exit
     - Performance-check failure
   * - Static
     - Fail trials
     - Fail trials
   * - Dense
     - Fail trials
     - Fail trials
   * - Chain
     - Preserve trials
     - Preserve trials
   * - Graph chain
     - Preserve trials
     - Preserve trials
   * - Most built-in prescreening tasks
     - Preserve trials
     - Fail trials

Static experiments commonly treat successful completion as a condition for
including a participant's dataset. Chain experiments instead preserve trials
by default because failing an earlier trial can invalidate substantial amounts
of downstream data. Built-in prescreening tasks generally preserve trials on
premature exit because they do not recruit to a target quantity of valid trial
data. Most retain the static default for performance-check failure;
``FreeTappingRecordTest`` explicitly preserves trials in both cases.


Failure propagation
-------------------

``propagate_failure`` controls dependency invalidation. It answers:

    If this trial fails, should downstream objects whose validity depends on it
    fail too?

It does not control whether participant failure should fail the trial in the
first place.

Propagation is particularly important for chain experiments. If a trial
contributes to the construction of a later chain node, failing that trial may
also require failing the dependent node and its descendants. This is why chain
TrialMakers preserve participant trials by default: bulk failure combined with
propagation could otherwise destroy a large part of a chain.

Experiment authors should enable propagation only where the validity of
downstream objects genuinely depends on the failed object. Ownership alone is
not a dependency: the fact that a participant owns several trials is not a
reason to propagate failure between those trials.


Policy summary
--------------

* Participant failure and trial failure are separate.
* Participant failure never globally cascades to every owned trial.
* Trial-local errors fail the affected trial.
* Participant-triggered invalidation is configured and scoped per TrialMaker.
* The configured choices are to preserve that TrialMaker's trials or fail all
  of them.
* Propagation concerns downstream dependencies, not participant ownership.
* Failed records are retained and exported for audit and analysis.
