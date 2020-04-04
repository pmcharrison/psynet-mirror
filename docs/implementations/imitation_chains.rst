.. _imitation_chains:

================
Imitation chains
================

An imitation-chain experiment depends on the four following classes:

* :class:`~dlgr_utils.trial.imitation_chain.ImitationChainSource`;
* :class:`~dlgr_utils.trial.imitation_chain.ImitationChainNode`;
* :class:`~dlgr_utils.trial.imitation_chain.ImitationChainTrial`;
* :class:`~dlgr_utils.trial.imitation_chain.ImitationChainMaker`.

You can define a custom imitation-chain experiment through the following steps:

1. Implement a subclass of :class:`~dlgr_utils.trial.imitation_chain.ImitationChainSource`
   that overrides the :meth:`~dlgr_utils.trial.imitation_chain.ImitationChainSource.generate_seed` method.
   This new method should generate the starting seed for the imitation chain.
   
2. Implement a subclass of :class:`~dlgr_utils.trial.imitation_chain.ImitationChainNode`
   that overrides the :meth:`~dlgr_utils.trial.imitation_chain.ImitationChainNode.summarise_trials` method.
   This new method should take a list of completed :class:`~dlgr_utils.trial.imitation_chain.ImitationChainTrial`
   objects as input and summarise the responses provided by the user,
   returning a seed that can be passed to the next node in the network.
   
3. Implement a subclass of :class:`~dlgr_utils.trial.imitation_chain.ImitationChainTrial`
   that overrides the 
   :meth:`~dlgr_utils.trial.imitation_chain.ImitationChainTrial.show_trial` method.
   If the trial numbers several pages, don't forget to update the 
   :attr:`~dlgr_utils.trial.imitation_chain.ImitationChainTrial.num_pages` attribute.
   
4. Create an instance of :class:`~dlgr_utils.trial.imitation_chain.ImitationChainMaker`,
   filling in its long constructor parameter list,
   and insert it into your experiment's timeline.
   
See the low-level documentation (below)
and the demo (``dlgr_utils/dlgr_utils/demos/imitation_chain``)
for more details.

.. automodule:: dlgr_utils.trial.imitation_chain
    :show-inheritance:
    :members:
    