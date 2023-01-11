.. _static:

==================
Static experiments
==================

This module implements a generic paradigm for a static trial-based experiment.
We simply assume that the experiment is organised around a finite number of stimuli 
for which we wish to elicit some kind of aggregated behavioural response.
This paradigm should be flexible enough to capture a range of standard 
perceptual experiment designs, but will need some customisation for more bespoke designs.

Implementing a static experiment in this framework comprises the following steps:

1. Write some Python code that represents each to-be-administered stimulus as a
   :class:`~psynet.trial.static.StimulusSpec` object.
   This object has a few important attributes;
   
   a. :attr:`~psynet.trial.static.StimulusSpec.definition` -
      This attribute is a dictionary holding the underlying parameters that define the stimulus
      that will be presented to the stimulus. For example, in a 3-choice 
      spot the odd-one-out pitch perception task, this attribute might hold 
      the fundamental frequency of the context tones
      and the fundamental frequency of the odd tone:
      
      ::
      
        {
            "context": 440,
            "oddity": 460
        }
    
   b. :attr:`~psynet.trial.static.StimulusSpec.phase` -
       This attribute defines the phase in which the stimulus will be administered,
       for example ``"training"`` or ``"main"``.
       
   c. :attr:`~psynet.trial.static.StimulusSpec.version_specs` -
       This optional attribute is a list of 
       :class:`~psynet.trial.static.StimulusVersionSpec`
       objects, each with another 
       :attr:`~psynet.trial.static.StimulusVersionSpec.definition`
       attribute in the form of a dictionary,
       which together define the multiple forms that a given stimulus 
       might take. The stimulus parameters held in 
       these :attr:`~psynet.trial.static.StimulusVersionSpec.definition`
       attributes correspond to incidental parameters that are thought 
       not to materially influence the true nature of the stimulus.
       A typical application is randomising the order of stimuli
       in a multiple choice task, or randomising the starting pitch
       of a tone sequence. An example value for this attribute would be 
       
       ::
       
            [
                StimulusVersionSpec{"oddity_position": 1},
                StimulusVersionSpec{"oddity_position": 2},
                StimulusVersionSpec{"oddity_position": 3}
            ]
       
       corresponding to the three possible positions of the odd-one-out in a 
       three-choice task.
       
   d. :attr:`~psynet.trial.static.StimulusSpec.participant_group` -
      This optional attribute limits the stimulus to a particular
      group of participants. If left at its default value, the stimulus
      will be available to all participants.
      
   e. :attr:`~psynet.trial.static.StimulusSpec.block` -
      This optional attribute assigns the stimulus to a particular block.
      Putting stimuli into blocks allows the researcher to constrain
      the ordering of stimuli within an experiment.
      
2. Create a new :class:`~psynet.trial.static.StimulusSet`
   object, passing it a list containing all of your stimulus definitions. 
      
3. Implement a subclass of :class:`~psynet.trial.static.StaticTrial`
   with a custom
   :meth:`~psynet.trial.static.StaticTrial.show_trial` method.
   This :meth:`~psynet.trial.static.StaticTrial.show_trial` method
   should produce an object of 
   class :class:`~psynet.timeline.Page` [1]_
   that administers the stimulus to the participant. 
   Through ``trial.definition``, this method has access to the underlying definition
   of the selected stimulus: this definition takes the form of a 
   dictionary that collects both the parameters from the relevant 
   :class:`~psynet.trial.static.StimulusSpec` definition
   and from the relevant :class:`~psynet.trial.static.StimulusVersionSpec`
   definition.
   This resulting :class:`~psynet.timeline.Page` object should
   elicit an answer representing the participant's response to the stimulus.
   
4. (Optional) Implement a 
   :meth:`~psynet.trial.static.StaticTrial.show_feedback` method
   for the custom :class:`~psynet.trial.static.StaticTrial`
   subclass. By interrogating ``participant.answer`` and comparing it 
   to ``trial.definition``, one can programmatically construct some feedback
   for the participant and present it as a 
   :class:`~psynet.timeline.Page` object.
      
5. Create an instance of :class:`~psynet.trial.static.StaticTrialMaker`,
   filling in its constructor parameter list
   with reference to the classes and objects you created above,
   and insert it into your experiment's timeline.

See the low-level documentation (below)
and the demo (``demos/static``)
for more details.

Further customization can be achieved by overriding the
:meth:`~psynet.trial.static.StaticTrialMaker.custom_stimulus_filter`
and :meth:`~psynet.trial.static.StaticTrialMaker.custom_stimulus_version_filter`
methods. This allows the experimenter to further restrict the stimuli and stimulus versions
available to the participant at a given point in the experiment.

.. [1] The :meth:`~psynet.trial.static.StaticTrial.show_trial` method
   may alternatively return a list of :class:`~psynet.timeline.Page` objects.
   In this case, the user is responsible for ensuring that the final
   page returns the appropriate ``answer``.
   The user should also specify an estimated number of pages in the
   :attr:`~psynet.trial.StaticTrial.num_pages` attribute.

.. automodule:: psynet.trial.static
    :show-inheritance:
    :members:
    :exclude-members: awaiting_async_process
    
