.. _mcmcp:

============================================
Markov Chain Monte Carlo with People (MCMCP)
============================================

A Markov Chain Monte Carlo with People (MCMCP)
experiment depends on the five following classes:

* :class:`~dlgr_utils.trial.mcmcp.MCMCPNetwork`
* :class:`~dlgr_utils.trial.mcmcp.MCMCPSource`;
* :class:`~dlgr_utils.trial.mcmcp.MCMCPNode`;
* :class:`~dlgr_utils.trial.mcmcp.MCMCPTrial`;
* :class:`~dlgr_utils.trial.mcmcp.MCMCPTrialMaker`.

You can define a custom imitation-chain experiment through the following steps:

1. Decide on a set of fixed parameters that will stay constant within 
   a chain but may change between chains. For example, one might 
   use a list with two presentation conditions, ``["fast", "slow"]``.
   Implement a subclass of :class:`~dlgr_utils.trial.mcmcp.MCMCPNetwork`
   with a custom :meth:`~dlgr_utils.trial.mcmcp.MCMCPNetwork.make_definition` method
   for choosing these fixed parameter values for a given chain. 
   The :meth:`~dlgr_utils.trial.chain.ChainNetwork.balance_across_networks` method 
   is typically useful here.
   
2. Decide on a set of free parameters that will define the parameter space
   for your chains. For example, one might use a tuple of three integers
   identifying an RGB colour (e.g. ``(255, 25, 0)``).
   Implement a subclass of :class:`~dlgr_utils.trial.mcmcp.MCMCPSource`
   with a custom :meth:`~dlgr_utils.trial.imitation_chain.MCMCPSource.generate_seed` method
   for generating the starting free parameter values for an MCMCP chain.
   
3. Implement a subclass of :class:`~dlgr_utils.trial.mcmcp.MCMCPTrial`
   with a custom
   :meth:`~dlgr_utils.trial.mcmcp.MCMCPTrial.show_trial` method.
   This :meth:`~dlgr_utils.trial.mcmcp.MCMCPTrial.show_trial` method
   should produce an object of 
   class :class:`~dlgr_utils.timeline.ResponsePage` [1]_
   that presents two stimuli in order, defined respectively by the free parameters
   stored in :attr:`~dlgr_utils.trial.mcmcp.MCMCPTrial.first_stimulus`
   and :attr:`~dlgr_utils.trial.mcmcp.MCMCPTrial.second_stimulus`,
   as well as the value of the network's fixed parameters
   stored in :attr:`~dlgr_utils.trial.mcmcp.MCMCPNetwork.definition`.
   Note that the order of the current state and the proposal is
   automatically randomised in advance,
   such that :attr:`~dlgr_utils.trial.mcmcp.MCMCPTrial.first_stimulus`
   may correspond either to the current state or to the proposal.
   The :class:`~dlgr_utils.timeline.ResponsePage` object should return an answer
   of ``0`` (or equivalently ``"0"``) if the participant selected the first stimulus in the pair,
   and ``1`` (or equivalently ``"1"``) if they selected the second stimulus in the pair.
   
4. (Optional) Implement a subclass of :class:`~dlgr_utils.trial.mcmcp.MCMCPNode`
   with a custom :meth:`~dlgr_utils.trial.mcmcp.MCMCPNode.summarise_trials` method.
   This new method should take a list of completed 
   :class:`~dlgr_utils.trial.mcmcp.MCMCPTrial` objects as input 
   and summarise the elicited answers,
   which can be found in the :attr:`~dlgr_utils.trial.answer` attribute
   of each :class:`~dlgr_utils.trial.mcmcp.MCMCPTrial` object.
   In conventional MCMCP, there is just one :class:`~dlgr_utils.trial.mcmcp.MCMCPTrial`
   per :class:`~dlgr_utils.trial.mcmcp.MCMCPNode`,
   and :meth:`~dlgr_utils.trial.mcmcp.MCMCPNode.summarise_trials` just returns
   the stimulus that was selected by the participant.
   This behaviour is implemented in the default implementation.
   However, if one wishes to increase the number of trials per node,
   then one will have to implement a custom 
   :meth:`~dlgr_utils.trial.mcmcp.MCMCPNode.summarise_trials` method.
   
5. Create an instance of :class:`~dlgr_utils.trial.mcmcp.MCMCPMaker`,
   filling in its constructor parameter list
   with reference to the classes you created above,
   and insert it into your experiment's timeline.
   
See the low-level documentation (below)
and the demo (``dlgr_utils/dlgr_utils/demos/mcmcp``)
for more details.

.. [1] The :meth:`~dlgr_utils.trial.mcmcp.MCMCPTrial.show_trial` method
   may alternatively return a list of :class:`~dlgr_utils.timeline.Page` objects.
   In this case, the user is responsible for ensuring that the 
   :attr:`dlgr_utils.participant.Participant.answer` attribute
   is set with the appropriate answer during this sequence.
   One way of achieving this is by including a 
   :class:`~dlgr_utils.timeline.ResponsePage` object in the event sequence.
   The user must also set the prespecify the number of pages in the 
   :attr:`~dlgr_utils.trial.mcmcp.MCMCPTrial.num_pages` attribute.

.. automodule:: dlgr_utils.trial.mcmcp
    :show-inheritance:
    :members:
    