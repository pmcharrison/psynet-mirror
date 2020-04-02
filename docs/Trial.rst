=======================
Trial-based experiments
=======================

The core part of many experiments is a sequence of *trials*
that are administered one after the other to the participant.
``dlgr_utils`` provides some helper classes for designing
such experiments. In particular, we consider the following scenarios
at increasing levels of specificity:

1. **Experiments using trials.**

2. **Experiments where trials are organised into networks.**

3. **Experiments where the networks take the form of chains.** 

4. **Specific paradigms such as generic non-adaptive experiments,
   Markov Chain Monte Carlo with People, iterated reproduction, 
   and Gibbs sampling**.

Each of these scenarios comes with a collection of classes already
implemented in ``dlgr_utils`` that help to organise the  
generic parts of the experiment, leaving you to focus on the 
details specific to your particular application.
We will now consider each of these scenarios in detail.

Experiments using trials
------------------------

At this most generic level, the two relevant classes are 
:class:`~dlgr_utils.trial.main.Trial` and
:class:`~dlgr_utils.trial.main.TrialGenerator`.
Each instance of the :class:`~dlgr_utils.trial.main.Trial`
object represents an individual trial, that is, 
some kind of stimulus presented to the participant
combined with the participant's response to that stimulus.
These objects are stored in the database.
The :class:`~dlgr_utils.trial.main.TrialGenerator`, meanwhile,
is inserted into the timeline to prompt the selection and 
administration of these trials to the participant.


.. autoclass:: dlgr_utils.trial.main.Trial
    :members:


These :class:`~dlgr_utils.trial.main.Trial` objects are 
stored in the database in the form of the Dallinger
:class:`~dallinger.models.Info` objects.

individual trials in the database,
where a trial 

Experiments where trials are organised into networks
----------------------------------------------------

Experiments where the networks take the form of chains
------------------------------------------------------

Specific paradigms
------------------
