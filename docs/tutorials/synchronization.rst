===============
Synchronization
===============

In some experiments we need to be able to synchronize certain groups of participants
to do the same things at the same time. For example, we might want to implement
a behavioral economics game where participants have to make certain kinds of decisions
and receive payouts depending on what the other participants in their group did.
PsyNet provides advanced synchronization utilities for supporting such experiments.

There are two main timeline constructs that are used to implement such synchronization.
The ``Grouper`` is responsible for creating groups of participants,
whereas the ``GroupBarrier`` is responsible for synchronizing participants within groups.

Grouper
-------

One straightforward type of ``Grouper`` is the ``SimpleGrouper``.
It may be included in the timeline as follows:

::

    SimpleGrouper(
        group_type="rock_paper_scissors",
        group_size=2,
    ),

This ``SimpleGrouper`` organizes participants into groups of 2. By default it will create a new
group of 2 each time 2 participants are ready and waiting, but an optional ``batch_size``
parameter can be used to delay group formation until more participants are waiting.

The groups created by ``Groupers`` are represented by ``SyncGroup`` objects.
If a participant is a member of just one active SyncGroup, then it can be accessed with
code as follows:

::

    participant.sync_group

If the participant is a member of multiple active SyncGroups, then they can be accessed
via ``participant.active_sync_groups``, which takes the form of a dictionary keyed by ``group_type``.
The full list of participants within the SyncGroup can then be accessed (and modified)
via ``sync_group.participants``, which is a list.

It is possible to put multiple ``Grouper`` constructs in a timeline.
If they have different ``group_type`` parameters then they will be used to create different grouping namespaces.
Groupers with the same ``group_type`` can be used to regroup the participants into different groupings
as they progress through the experiment.
However, it is not possible to be in multiple groups with the same ``group_type`` simultaneously;
one must place a ``GroupCloser`` in the timeline to close the group before assigning the participants
to a new one.


Group Barrier
-------------

A Group Barrier may be included in the timeline as follows:

::

    GroupBarrier(
        id_="finished_trial",
        group_type="rock_paper_scissors",
        on_release=self.score_trial,
    )


When participants reach this barrier, they will be told to wait until all participants in their group
are also waiting at that barrier. An optional ``on_release`` function can be provided to the barrier,
which will be executed on the group of participants at the point when they leave the barrier.


Synchronization in trial makers
-------------------------------

It is perfectly possible to use these synchronization constructs within trial makers.
In this case, it is usually wise to provide a ``sync_group_type`` argument to the trial maker,
for example:

::

    RockPaperScissorsTrialMaker(
        id_="rock_paper_scissors",
        trial_class=RockPaperScissorsTrial,
        nodes=[
            StaticNode(definition={"color": color})
            for color in ["red", "green", "blue"]
        ],
        expected_trials_per_participant=3,
        max_trials_per_participant=3,
        sync_group_type="rock_paper_scissors",
    )

This tells the trial maker to synchronize the logic of assigning participants to nodes according to their
SyncGroup. By default, each group has a randomly assigned leader; node allocation is determined
by standard PsyNet logic for that leader, as if that person were taking that trial maker by themselves;
the other participants in that group then 'follow' that leader, being assigned to the same nodes as the leader
on each trial.

Using a ``sync_group_type`` parameter means that the beginning of each trial is synchronized across all participants
within a given group. It is possible to synchronize other parts of the trial by including further
GroupBarriers within the trial, for example:

::

    def show_trial(self, experiment, participant):
        return join(
            GroupBarrier(
                id_="wait_for_trial",
                group_type="rock_paper_scissors",
            ),
            self.choose_action(color=self.definition["color"]),
            GroupBarrier(
                id_="finished_trial",
                group_type="rock_paper_scissors",
                on_release=self.score_trial,
            ),
        )

Demo
----

The 'rock, paper, scissors' demo provides an example of the full-scale use of these features.
The source code is provided below:

.. literalinclude:: ../../demos/rock_paper_scissors/experiment.py
   :language: python
