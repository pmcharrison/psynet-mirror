=======================
Trial-based experiments
=======================

The core part of many experiments is a sequence of trials
that are administered one after the other to the participant.
``dlgr_utils`` provides some helper classes for designing
such experiments. In particular, we consider the following scenarios
at increasing levels of specificity:

1. :ref:`Experiments using trials`.

2. :ref:`Experiments where trials are organised into networks`.

3. :ref:`Experiments where the networks take the form of chains`. 

4. :ref:`Specific paradigms` such as generic non-adaptive experiments,
   *Markov Chain Monte Carlo with People*, *iterated reproduction*, 
   and *Gibbs sampling*.

Each of these scenarios comes with a collection of classes already
implemented in ``dlgr_utils`` that help to organise the  
generic parts of the experiment, leaving you to focus on the 
details specific to your particular application.
We will now consider each of these scenarios in detail.

Experiments using trials
------------------------

At this most generic level, the two relevant classes are 
:class:`~dlgr_utils.trial.main.Trial` and
:class:`~dlgr_utils.trial.main.TrialMaker`.
Each instance of the :class:`~dlgr_utils.trial.main.Trial`
object represents an individual trial, that is, 
some kind of stimulus presented to the participant
combined with the participant's response to that stimulus.
These objects are stored in the database.
The :class:`~dlgr_utils.trial.main.TrialMaker`, meanwhile,
is inserted into the timeline to prompt the selection and 
administration of these trials to the participant.

When designing an experiment at this level, 
the user must create custom subclasses of
:class:`~dlgr_utils.trial.main.Trial`
and :class:`~dlgr_utils.trial.main.TrialMaker`
that implement the desired logic for their experiment.
The subclass of :class:`~dlgr_utils.trial.main.Trial` should
implement the following methods:

* :meth:`~dlgr_utils.trial.main.Trial.make_definition`,
  responsible for deciding on the content of the trial.
* :meth:`~dlgr_utils.trial.main.Trial.show_trial`,
  determines how the trial is turned into a webpage for presentation to the participant.
* :meth:`~dlgr_utils.trial.main.Trial.show_feedback`.
  defines an optional feedback page to be displayed after the trial.

See the :class:`~dlgr_utils.trial.main.Trial` documentation for details.

The subclass of :class:`~dlgr_utils.trial.main.TrialMaker`
should implement one method in particular:
:meth:`~dlgr_utils.trial.main.TrialMaker.prepare_trial`.
This method is responsible for constructing an appropriate
:class:`~dlgr_utils.trial.main.Trial` object to 
administer to that participant at that part of the experiment.
See the :class:`~dlgr_utils.trial.main.TrialMaker` documentation for details.

Currently we don't have any demos for this most generic level of experiment design;
all our demos use more specific levels described below.

Experiments where trials are organised into networks
----------------------------------------------------

For designing an experiment where trials are organised into networks,
you can still use the original :class:`~dlgr_utils.trial.main.Trial` class,
but we recommend you use (either directly or subclassing) the 
:class:`~dlgr_utils.trial.main.NetworkTrialMaker` class
as the trial maker,
and the :class:`~dlgr_utils.trial.main.TrialNetwork` class
for the networks.
These classes automate certain
common aspects of network-based experiments.

These experiments are organised around networks
in an analogous way to the network-based experiments in Dallinger.
A :class:`~dallinger.models.Network` comprises a collection of 
:class:`~dallinger.models.Node` objects organised in some kind of structure.
Here the role of :class:`~dallinger.models.Node` objects 
is to generate :class:`~dallinger.models.Trial` objects.
Typically the :class:`~dallinger.models.Node` object represents some 
kind of current experiment state, such as the last datum in a transmission chain.
In some cases, a :class:`~dallinger.models.Network` or a :class:`~dallinger.models.Node`
will be owned by a given participant; in other cases they will be shared 
between participants.

An important feature of these networks is that their structure can change 
over time. This typically involves adding new nodes that somehow 
respond to the trials that have been submitted previously.

The present class facilitates this behaviour by providing
a built-in :meth:`~dlgr_utils.trial.main.TrialMaker.prepare_trial`
implementation that comprises the following steps:

1. Find the available networks from which to source the next trial,
   ordered by preference
   (:meth:`~dlgr_utils.trial.main.NetworkTrialMaker.find_networks`).
   These may be created on demand, or alternatively pre-created by
   :meth:`~dlgr_utils.trial.main.NetworkTrialMaker.experiment_setup_routine`.
2. Give these networks an opportunity to grow (i.e. update their structure
   based on the trials that they've received so far)
   (:meth:`~dlgr_utils.trial.main.NetworkTrialMaker.grow_network`).
3. Iterate through these networks, and find the first network that has a 
   node available for the participant to attach to.
   (:meth:`~dlgr_utils.trial.main.NetworkTrialMaker.find_node`).
4. Create a trial from this node
   (:meth:`dlgr_utils.trial.main.Trial.__init__`).
   
The trial is then administered to the participant, and a response elicited.
Once the trial is finished, the network is given another opportunity to grow.

The implementation also provides support for asynchronous processing,
for example to prepare the stimuli available at a given node,
or to postprocess trials submitted to a given node.
There is some sophisticated logic to make sure that a 
participant is not assigned to a :class:`~dallinger.models.Node` object 
if that object is still waiting for an asynchronous process,
and likewise a trial won't contribute to a growing network if 
it is still pending the outcome of an asynchronous process.

See :class:`~dlgr_utils.trial.main.NetworkTrialMaker` 
and :class:`~dlgr_utils.trial.main.TrialNetwork` for more details.

Experiments where the networks take the form of chains
------------------------------------------------------

A common network structure is the *chain*. A chain comprises a series of nodes
connecting in a serial order. Many complex experiment designs can be expressed
as chains, for example:

* Iterated reproduction;
* Markov Chain Monte Carlo with People;
* Gradient Descent over People;
* Computerised adaptive testing.

The following classes are provided to help this process,
which can be subclassed to implement a particular paradigm:

* :class:`~dlgr_utils.trial.chain.ChainTrialMaker`,
  a special type of :class:`~dlgr_utils.trial.main.ChainTrialMaker`;

* :class:`~dlgr_utils.trial.chain.ChainNetwork`,
  a special type of :class:`~dlgr_utils.trial.main.TrialNetwork`;

* :class:`~dlgr_utils.trial.chain.ChainNode`,
  a special type of :class:`dallinger.models.Node`;

* :class:`~dlgr_utils.trial.chain.ChainTrial`,
  a special type of :class:`~dlgr_utils.trial.main.NetworkTrial`;

* :class:`~dlgr_utils.trial.chain.ChainSource`,
  a special type of :class:`dallinger.nodes.Source`, 
  providing the initial network state.
   
To implement a new paradigm using these helper classes,
we recommend that you create new classes that subclass each of the
helper classes listed above. Follow their documentation to understand
which methods you need to override and what customisable options
there are.

Specific paradigms
------------------
