Participant and trial failure
=============================

PsyNet distinguishes participant failure from trial failure. These concepts are
related, but they describe different things:

* A failed **participant** has been explicitly marked as failed by PsyNet,
  normally because they should not continue or count as a successful
  completion.
* A failed **trial** is a retained trial record that should be excluded from the
  experiment's usable dataset. Fail a trial when something is wrong with that
  record (timeout, analysis failure, an unfinished trial left after exit, or a
  quality check that says the responses are unusable). Do not fail submitted
  trials just because the person left.
* **Failure propagation** determines whether failing one object should also
  invalidate objects that depend on it.

In practice: if someone leaves or is failed, PsyNet fails their **incomplete**
trials and keeps their **completed** trials, unless a performance check on that
TrialMaker says the completed responses are bad. Recruitment quotas use
``n_participants`` or ``n_trials``, not trial failure.

Participant failure is not the inverse of completion. A participant who has
not reached the end but remains able to continue is incomplete, not failed.

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
data exports, together with their ``failed`` and ``failed_reason`` fields. Trial
failure instead means that the record should not contribute to normal analysis,
balancing, recruitment targets, or downstream experimental logic. For example,
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

A trial should be failed when the trial itself is unusable, or when it
depends on another failed object.

Examples include:

* a response timeout;
* failed recording analysis or required post-processing;
* a duplicate or structurally inconsistent trial;
* an incomplete trial left behind when the participant exits or is failed;
* a performance check that means this TrialMaker's responses are unusable;
* custom experiment logic that determines that a response is unusable.

These cases fail the affected trials. They do not, by themselves, fail every
completed trial belonging to the participant. A premature exit in particular
fails incomplete trials and leaves completed trials in place. Recruitment
quotas are configured separately (``n_participants`` or ``n_trials``), not by
failing submitted trials from people who left.


Participant failure
-------------------

Calling :meth:`~psynet.participant.Participant.fail` marks the participant as
failed and runs the experiment's registered participant-failure routines. It
does not inherently fail the participant's completed trials.

It also takes them off the main timeline. PsyNet redirects the participant to
the ``unsuccessful_end`` branch, so they see an early-end page instead of
continuing through later experiment pages. The redirect is skipped if they are
already in an end branch or have already completed the experiment. You can
customise that branch; see :doc:`Timelines <../getting_started/timelines>`.

The redirect timing depends on where ``fail()`` is called:

* From within the page-advance loop, for example from a
  :class:`~psynet.timeline.CodeBlock`, the jump to ``unsuccessful_end`` is
  immediate.
* From a background process, for example a timeout, recruiter notification, or
  admin action, the redirect is queued as ``participant.pending_redirect`` and
  applied the next time the participant submits a response. That preserves the
  answer they are currently giving.

Incomplete trials (``complete=False``) are always failed on any participant
failure, including premature exit. They are not usable contributions and can
otherwise stall dependent logic such as chain growth.

Completed trials stay unless a TrialMaker's performance-check policy says
those responses are unusable. ``fail_trials_on_participant_performance_check``
controls that. Enable it when the check is evidence that this TrialMaker's
data should be excluded (bots, nonsense responses, failed attention checks).
Leave it off when the check only gates eligibility to continue, for example
many prescreens, so that the collected trials remain valid measurements.

Premature exit does not fail completed trials. Recruiter events that end a
still-eligible participant (assignment abandonment, a marketplace return such
as a Prolific return, or reassignment) mark the participant as failed with
the ``premature_exit`` tag, fail incomplete trials, and leave completed
trials in place. If the participant has already failed or completed, PsyNet
only records the recruiter cause tag (for example ``assignment_returned``)
and does not invent a second ``premature_exit`` or re-run trial-invalidation
logic. That covers settlement returns after an unsuccessful end, such as
return-for-bonus.

The default performance-check policies are:

.. list-table::
   :header-rows: 1

   * - TrialMaker
     - Premature exit
     - Performance-check failure
   * - Static
     - Fail incomplete trials only
     - Fail completed trials
   * - Dense
     - Fail incomplete trials only
     - Fail completed trials
   * - Chain
     - Fail incomplete trials only
     - Preserve completed trials
   * - Graph chain
     - Fail incomplete trials only
     - Preserve completed trials
   * - Most built-in prescreening tasks
     - Fail incomplete trials only
     - Fail completed trials

Chain TrialMakers preserve completed trials on performance-check failure by
default because failing an earlier trial can invalidate substantial amounts
of downstream data. Built-in prescreening tasks generally keep completed
trials on premature exit for the same reason everyone else does: those
trials are not errors. Most retain the static default for performance-check
failure; ``FreeTappingRecordTest`` explicitly preserves completed trials in
both cases.


Choosing a participant failure policy
-------------------------------------

``fail_trials_on_participant_performance_check`` is a data-quality switch, not
a recruitment switch. Set it to ``True`` when failing the check means this
TrialMaker's completed responses should not be analyzed. Set it to ``False``
when the check only decides whether the participant may continue.

Do not fail completed trials in order to control how many people or ratings
you recruit. Use ``recruit_mode="n_participants"`` or ``"n_trials"`` for that.

These policies are independent for each TrialMaker. A prescreen can preserve
completed trials as evidence of ineligibility while a later static task
invalidates its own trials after a quality failure.


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


Participant-scoped networks
---------------------------

Within-participant chains remain alive after the owning participant fails.
``failed`` means the object's content should not be used, not that a private
chain has been retired. Those networks are unused once their owner is gone,
but PsyNet does not fail their nodes solely to mark them inactive. Completed
trials on those chains still follow the performance-check setting above.
