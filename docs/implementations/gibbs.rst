.. _gibbs:

==========================
Gibbs Sampling with People
==========================

A Gibbs Sampling with People
experiment depends on the five following classes:

* :class:`~psynet.trial.gibbs.GibbsNetwork`
* :class:`~psynet.trial.gibbs.GibbsSource`;
* :class:`~psynet.trial.gibbs.GibbsNode`;
* :class:`~psynet.trial.gibbs.GibbsTrial`;
* :class:`~psynet.trial.gibbs.GibbsTrialMaker`.

You can define a custom Gibbs sampling experiment through the following steps:

1. Decide on a set of fixed parameters that will stay constant within 
   a chain but may change between chains. For example, one might 
   use a list with three targets, ``["forest", "rock", "carrot"]``.
   Implement a subclass of :class:`~psynet.trial.gibbs.GibbsNetwork`
   with a custom :meth:`~psynet.trial.gibbs.GibbsNetwork.make_definition` method
   for choosing these fixed parameter values for a given chain. 
   The :meth:`~psynet.trial.chain.ChainNetwork.balance_across_networks` method 
   is typically useful here.
   
2. Decide on a vector of free parameters that will define the parameter space
   for your chains. This vector will be represented as a list;
   for example, one might use a list of three integers
   identifying an RGB color (e.g. ``[255, 25, 0]``).
   Take the length of this vector and save it in the ``vector_length`` class attribute
   for your custom :class:`~psynet.trial.gibbs.GibbsNetwork` class.
   
3. In the same custom :class:`~psynet.trial.gibbs.GibbsNetwork` class,
   implement a custom :meth:`~psynet.trial.gibbs.GibbsNetwork.random_sample` method
   for randomly sampling parameter values for each position ``i`` in your vector.
   This will be used to initialise the free parameters for different chains,
   and for sampling the starting positions of the user response options.
   
4. Implement a subclass of :class:`~psynet.trial.gibbs.GibbsTrial`
   with a custom
   :meth:`~psynet.trial.gibbs.GibbsTrial.show_trial` method.
   This :meth:`~psynet.trial.gibbs.GibbsTrial.show_trial` method
   should produce an object of 
   class :class:`~psynet.timeline.Page` [1]_
   that presents the participant with some dynamic stimulus (e.g. a color
   or a looping audio sample) that jointly
   
   a) Embodies the fixed network parameter, e.g. ``"forest"``, found in ``trial.network.definition``;
   b) Embodies the free network parameters, e.g. ``[255, 25, 0]``, found in ``trial.initial_vector``;
   c) Listens to some kind of response interface, e.g. an on-screen slider, which manipulates
      the value of the ith free network parameter, where i is defined from ``trial.active_index``.
   d) Returns the chosen value of the free network parameter as an ``answer``.

5. Import the :class:`~psynet.trial.gibbs.GibbsNode` class; typicaly this will not 
   need to be customised.
   
6. Import the :class:`~psynet.trial.gibbs.GibbsSource` class; typicaly this will not 
   need to be customised.

7. Create an instance of :class:`~psynet.trial.gibbs.GibbsMaker`,
   filling in its constructor parameter list
   with reference to the classes you created above,
   and insert it into your experiment's timeline.
   
See the low-level documentation (below)
and the demo (``demos/gibbs``)
for more details.

Note: you can customize the assignment of participants to chains by overriding the
:meth:`~psynet.trial.gibbs.GibbsTrialMaker.custom_network_filter` method.

.. [1] The :meth:`~psynet.trial.gibbs.GibbsTrial.show_trial` method
   may alternatively return a list of :class:`~psynet.timeline.Page` objects.
   In this case, the user is responsible for ensuring that the final
   page returns the appropriate ``answer``.
   The user should also specify an estimated number of pages in the
   :attr:`~psynet.trial.gibbs.GibbsTrial.num_pages` attribute.

.. automodule:: psynet.trial.gibbs
    :show-inheritance:
    :members:
    
