.. _mcmcp:

============================================
Markov Chain Monte Carlo with People (MCMCP)
============================================

A Markov Chain Monte Carlo with People (MCMCP)
experiment depends on the five following classes:

* :class:`~psynet.trial.mcmcp.MCMCPNetwork`
* :class:`~psynet.trial.mcmcp.MCMCPSource`;
* :class:`~psynet.trial.mcmcp.MCMCPNode`;
* :class:`~psynet.trial.mcmcp.MCMCPTrial`;
* :class:`~psynet.trial.mcmcp.MCMCPTrialMaker`.

You can define a custom MCMCP experiment through the following steps:

1. Decide on a set of fixed parameters that will stay constant within 
   a chain but may change between chains. For example, one might 
   use a list with two presentation conditions, ``["fast", "slow"]``.
   Implement a subclass of :class:`~psynet.trial.mcmcp.MCMCPNetwork`
   with a custom :meth:`~psynet.trial.mcmcp.MCMCPNetwork.make_definition` method
   for choosing these fixed parameter values for a given chain. 
   The :meth:`~psynet.trial.chain.ChainNetwork.balance_across_networks` method 
   is typically useful here.
   
2. Decide on a set of free parameters that will define the parameter space
   for your chains. For example, one might use a tuple of three integers
   identifying an RGB colour (e.g. ``(255, 25, 0)``).
   Implement a subclass of :class:`~psynet.trial.mcmcp.MCMCPSource`
   with a custom :meth:`~psynet.trial.mcmcp.MCMCPSource.generate_seed` method
   for generating the starting free parameter values for an MCMCP chain.
   
3. Implement a subclass of :class:`~psynet.trial.mcmcp.MCMCPTrial`
   with a custom
   :meth:`~psynet.trial.mcmcp.MCMCPTrial.show_trial` method.
   This :meth:`~psynet.trial.mcmcp.MCMCPTrial.show_trial` method
   should produce an object of 
   class :class:`~psynet.timeline.Page` [1]_
   that presents two stimuli in order, defined respectively by the free parameters
   stored in :attr:`~psynet.trial.mcmcp.MCMCPTrial.first_stimulus`
   and :attr:`~psynet.trial.mcmcp.MCMCPTrial.second_stimulus`,
   as well as the value of the network's fixed parameters
   stored in :attr:`~psynet.trial.mcmcp.MCMCPNetwork.definition`.
   Note that the order of the current state and the proposal is
   automatically randomised in advance,
   such that :attr:`~psynet.trial.mcmcp.MCMCPTrial.first_stimulus`
   may correspond either to the current state or to the proposal.
   The :class:`~psynet.timeline.Page` object should return an answer
   of ``0`` (or equivalently ``"0"``) if the participant selected the first stimulus in the pair,
   and ``1`` (or equivalently ``"1"``) if they selected the second stimulus in the pair.
   
4. Implement a subclass of :class:`~psynet.trial.mcmcp.MCMCPNode`
   with a custom :meth:`~psynet.trial.mcmcp.MCMCPNode.get_proposal` method.
   This method should take set of free parameter values (provided in the ``state`` argument)
   and generate a proposed new set of free parameter values
   in the neighbourhood of these original values.

5. (Optional) Add a custom :meth:`~psynet.trial.mcmcp.MCMCPNode.summarise_trials` method
   to the :class:`~psynet.trial.mcmcp.MCMCPNode` class defined in the previous step.
   This new method should take a list of completed 
   :class:`~psynet.trial.mcmcp.MCMCPTrial` objects as input 
   and summarise the elicited answers,
   which can be found in the :attr:`~psynet.trial.answer` attribute
   of each :class:`~psynet.trial.mcmcp.MCMCPTrial` object.
   In conventional MCMCP, there is just one :class:`~psynet.trial.mcmcp.MCMCPTrial`
   per :class:`~psynet.trial.mcmcp.MCMCPNode`,
   and :meth:`~psynet.trial.mcmcp.MCMCPNode.summarise_trials` just returns
   the stimulus that was selected by the participant.
   This behaviour is implemented in the default implementation.
   However, if one wishes to increase the number of trials per node,
   then one will have to implement a custom 
   :meth:`~psynet.trial.mcmcp.MCMCPNode.summarise_trials` method.
   
6. Create an instance of :class:`~psynet.trial.mcmcp.MCMCPMaker`,
   filling in its constructor parameter list
   with reference to the classes you created above,
   and insert it into your experiment's timeline.
   
See the low-level documentation (below)
and the demo (``demos/mcmcp``)
for more details.

.. [1] The :meth:`~psynet.trial.mcmcp.MCMCPTrial.show_trial` method
   may alternatively return a list of :class:`~psynet.timeline.Page` objects.
   In this case, the user is responsible for ensuring that the 
   :attr:`psynet.participant.Participant.answer` attribute
   is set with the appropriate answer during this sequence.
   One way of achieving this is by including a 
   :class:`~psynet.timeline.Page` object in the event sequence.
   The user should also specify an estimated number of pages in the
   :attr:`~psynet.trial.mcmcp.MCMCPTrial.num_pages` attribute.

.. automodule:: psynet.trial.mcmcp
    :show-inheritance:
    :members:
    
