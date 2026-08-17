Participant and trial failure
=============================

PsyNet distinguishes participant failure from trial failure. These concepts are
related, but they describe different things:

* A failed **participant** has been explicitly marked as failed by PsyNet,
  normally because they should not continue or count as a successful
  completion.
* A failed **trial** is a retained trial record that should be excluded from the
  experiment's usable dataset.
* **Failure propagation** determines whether failing one object should also
  invalidate objects that depend on it.

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

PsyNet currently recognizes two participant failure causes for automatic
invalidation of **completed** trials:

``premature_exit``
    Controlled by ``fail_trials_on_premature_exit``.

``performance_check``
    Controlled by ``fail_trials_on_participant_performance_check``.

If the corresponding option is ``True``, all non-failed trials belonging to
that participant and TrialMaker are failed. This includes completed and
finalized trials. If it is ``False``, completed trials are preserved.
Incomplete trials (``complete=False``) are always failed on any participant
failure, because they are not usable contributions and can otherwise stall
dependent logic such as chain growth or synchronous barriers. Participant
failure for any other reason therefore clears incomplete trials but preserves
completed ones unless custom failure logic explicitly fails them.

Recruiter events count as premature exit. When a recruiter reports that a
participant abandoned, returned, or had their assignment reassigned while
still able to take part (for example a submission returned on Prolific),
PsyNet marks the participant as failed with the ``premature_exit`` tag.
Trial invalidation then follows each TrialMaker's
``fail_trials_on_premature_exit`` setting for completed trials, exactly as
for any other premature exit; the recruiter event does not decide trial
validity on its own. If the participant has already failed or completed,
PsyNet only records the recruiter cause tag (for example
``assignment_returned``) and does not invent a second ``premature_exit`` or
re-run trial-invalidation logic. That covers settlement returns after an
unsuccessful end, such as return-for-bonus.

A performance check is a participant-level quality decision. It can represent poor task performance,
insufficiently grammatical responses, failed attention checks, or signs of
automated or bot behavior. When a participant receives the
``performance_check`` failure tag, every registered TrialMaker applies its own
``fail_trials_on_participant_performance_check`` setting. A TrialMaker should
enable this setting when such participant-level evidence means that its trials
should be excluded from the usable dataset.

The default policies reflect the different data dependencies of each paradigm:

.. list-table::
   :header-rows: 1

   * - TrialMaker
     - Premature exit
     - Performance-check failure
   * - Static
     - Fail completed trials
     - Fail completed trials
   * - Dense
     - Fail completed trials
     - Fail completed trials
   * - Chain
     - Preserve completed trials
     - Preserve completed trials
   * - Graph chain
     - Preserve completed trials
     - Preserve completed trials
   * - Most built-in prescreening tasks
     - Preserve completed trials
     - Fail completed trials

Static experiments commonly treat successful completion as a condition for
including a participant's dataset. This is because it can cause trouble for
standard data analyses if such datasets contain partial contributions.
Chain experiments instead preserve completed trials
by default because failing an earlier trial can invalidate substantial amounts
of downstream data. Incomplete trials are still failed so they cannot stall
chain growth. Built-in prescreening tasks generally preserve completed trials on
premature exit because they do not recruit to a target quantity of valid trial
data. Most retain the static default for performance-check failure;
``FreeTappingRecordTest`` explicitly preserves completed trials in both cases.


Choosing a participant failure policy
-------------------------------------

The participant failure options express data-inclusion policy. They should be
chosen according to which records the experimenter would be willing to analyze
or count toward a recruitment target.

Set ``fail_trials_on_premature_exit=True`` when the experiment requires
complete-participant data. For example, an experiment targeting 30 ratings per
stimulus might require all 30 ratings to come from participants who completed
the experiment. Failing completed trials from premature exits prevents those
partial ratings from contributing to the target, so PsyNet recruits
replacements. Set it to ``False`` when valid completed partial contributions
should remain usable. Incomplete trials are failed on any participant failure.

Set ``fail_trials_on_participant_performance_check=True`` when failing the
performance check is evidence that this TrialMaker's data should not be
analyzed, for example because the participant responded nonsensically or showed
signs of bot behavior. Set it to ``False`` when the check only determines
eligibility to continue and the collected completed trials remain meaningful.
Incomplete trials are failed on any participant failure. A failed
prescreen can therefore preserve completed trials when those trials are valid
measurements of ineligibility.

These policies are intentionally independent for each TrialMaker. In an
experiment containing several TrialMakers, one can preserve useful partial
contributions while another excludes data unless the participant completes and
passes its quality checks.


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

Within-participant chains (and other networks whose ``participant_id`` is set)
belong only to that participant. When the participant fails, PsyNet fails those
networks and their nodes so they do not remain alive for growth checks or
dashboards. Across-participant networks are left untouched. This structural
cleanup does not by itself fail trials; completed-trial invalidation still
follows the TrialMaker settings above.
