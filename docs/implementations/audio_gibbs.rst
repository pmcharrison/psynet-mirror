.. _audio_gibbs:

================================
Audio Gibbs Sampling with People
================================

An Audio Gibbs Sampling with People
experiment depends on the five following classes:

* :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork`
* :class:`~psynet.trial.audio_gibbs.AudioGibbsSource`;
* :class:`~psynet.trial.audio_gibbs.AudioGibbsNode`;
* :class:`~psynet.trial.audio_gibbs.AudioGibbsTrial`;
* :class:`~psynet.trial.audio_gibbs.AudioGibbsTrialMaker`.

You can define a custom Audio Gibbs sampling experiment through the following steps:

1. Decide on a set of fixed parameters that will stay constant within
   a chain but may change between chains. For example, one might
   use a list with three targets, ``["suggestive", "angry", "kind"]``.
   Implement a subclass of :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork`
   with a custom :meth:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.make_definition` method
   for choosing these fixed parameter values for a given chain.
   The :meth:`~psynet.trial.chain.ChainNetwork.balance_across_networks` method
   is typically useful here.

2. Decide on a vector of free parameters that will define the parameter space
   for your chains. This vector will be represented as a list;
   for example, one might use a list of three integers
   identifying an RGB colour (e.g. ``[255, 25, 0]``).
   Take the length of this vector and save it in the
   :attr:``~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_length`` attribute
   for your custom :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork` class.

3. Decide on the permitted ranges for these free parameters
   and express these ranges as a list, where the ith element is a list of length 2
   expresses the minimum and maximum value for the ith parameter respectively.
   Save this list in the
   :attr:``~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_ranges`` attribute
   for your custom :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork` class.

4. Decide on the granularity for audio synthesis (i.e. how many audio files will
   be synthesised for each trial), and save this value in the
   :attr:``~psynet.trial.audio_gibbs.AudioGibbsNetwork.granularity`` attribute
   for your custom :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork` class.

5. Implement a synthesis function that generates an audio file according to
   a numeric vector of parameters. This function should exist in a module
   that can be imported by the experiment.
   Save a reference to this function in the
   :attr:``~psynet.trial.audio_gibbs.AudioGibbsNetwork.synth_function`` attribute
   for your custom :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork` class
   (see the documentation for more details).

6. Decide on an S3 bucket in which to store your stimuli.
   Save the name of this bucket in the
   :attr:``~psynet.trial.audio_gibbs.AudioGibbsNetwork.s3_bucket`` attribute
   for your custom :class:`~psynet.trial.audio_gibbs.AudioGibbsNetwork` class.

5. Implement a subclass of :class:`~psynet.trial.audio_gibbs.AudioGibbsTrial`
   with a custom
   :meth:`~psynet.trial.audio_gibbs.AudioGibbsTrial.get_prompt` method.
   This :meth:`~psynet.trial.audio_gibbs.AudioGibbsTrial.get_prompt` method
   should determine the prompt shown to the user above their slider.

6. Import the :class:`~psynet.trial.audio_gibbs.AudioGibbsNode` class; typicaly this will not
   need to be customised.

7. Import the :class:`~psynet.trial.audio_gibbs.AudioGibbsSource` class; typicaly this will not
   need to be customised.

8. Create an instance of :class:`~psynet.trial.audio_gibbs.AudioGibbsMaker`,
   filling in its constructor parameter list
   with reference to the classes you created above,
   and insert it into your experiment's timeline.

See the low-level documentation (below)
and the demo (``psynet/psynet/demos/audio_gibbs``)
for more details.

.. automodule:: psynet.trial.audio_gibbs
    :show-inheritance:
    :members:
