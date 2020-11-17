.. _developer:
.. highlight:: shell

============================
Creating pre-screening tasks
============================

Have a look at the below examples and add a new class specifying your new pre-screening task in the file ``psynet/prescreen.py``.

A simple pre-screening task
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In general, a pre-screening task is a :class:`~psynet.trial.Module` which contains some conditional logic for determining the participant's suitability for an experiment.

In the following we show an example of a pre-screening task that consists of a single Yes/No question checking for the participant's suitability for a follow-up hearing test.

The ``HearingImpairmentCheck`` class inherits from :class:`~psynet.trial.Module` and defines the actual pre-screening. It has a single event (:class:`~psynet.trial.Module`) assigned to its ``events`` property which consists of a ``label``, a :class:`~psynet.timeline.Page` (:class:`~psynet.page.NAFCPage`) for the participant's input and the logic (:class:`~psynet.timeline.conditional`) to determine a positive or negative outcome. In the negative case the :class:`~psynet.page.UnsuccessfulEndPage` is shown and the participant exits the pre-screening. This class also needs to be provided with values for ``label`` and ``time_estimate_per_trial``.

::

    import psynet.experiment
    from psynet.page import InfoPage, NAFCPage, SuccessfulEndPage, UnsuccessfulEndPage
    from psynet.timeline import Module, Timeline, conditional, join

    class HearingImpairmentCheck(Module):
        def __init__(
                self,
                label = "hearing_impairment_check",
                time_estimate_per_trial: float = 3.0,
            ):
            self.label = label
            self.events = join(
                NAFCPage(
                    label = self.label,
                    prompt="Do you have any kind of hearing impairment? (I.e., do you have any problems with your hearing?)",
                    choices=["Yes", "No"],
                    time_estimate=time_estimate_per_trial
                ),
                conditional(
                    "hearing_impairment_check",
                    lambda experiment, participant: participant.answer == "Yes",
                    UnsuccessfulEndPage(failure_tags=["hearing_impairment_check"])
                )
            )
            super().__init__(self.label, self.events)

\* Another simple example would be a :class:`~psynet.page.TextInputPage` where the text provided by the participant is evaluated by some logic determining the positive/negative outcome.

A pre-screening task can then be included in an experiment as follows:

::

    import psynet.experiment
    from psynet.page import InfoPage, SuccessfulEndPage
    from psynet.timeline import Timeline
    # code for importing HearingImpairmentCheck

    class Exp(psynet.experiment.Experiment):
        timeline = Timeline(
            HearingImpairmentCheck(),
            InfoPage("Congratulations! You have no hearing impairment.", time_estimate=3),
            SuccessfulEndPage()
        )

    extra_routes = Exp().extra_routes()


For more advanced examples, please refer to the source code of the three non-adaptive pre-screening tasks :class:`~psynet.prescreen.ColorVocabularyTest`, :class:`~psynet.prescreen.ColorVocabularyTest`, and :class:`~psynet.prescreen.HeadphoneCheck` presented above or continue to the next section where we provide some boilerplate code for building non-adaptive pre-screening tasks.

Non-adaptive pre-screening tasks (Boilerplate code)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this section we provide code snippets for building non-adaptive pre-screening tasks utilizing :class:`~psynet.trial.main.TrialMaker` and :class:`~psynet.trial.non_adaptive.StimulusSet`.

A non-adaptive pre-screening task is a class which inherits from :class:`~psynet.trial.Module`, e.g.:

::

    from psynet.timeline import Module, join

    class SomeNonAdaptivePrescreeningTask(Module):
        def __init__(
            self,
            label = "some_non-adaptive_prescreening_task",
            time_estimate_per_trial: float = 5.0,
            performance_threshold: int = 4,
        ):
        self.label = label
        self.events = join(
            self.instruction_page(),
            self.trial_maker(performance_threshold)
        )
        super().__init__(self.label, self.events)


Set reasonable defaults for ``time_estimate_per_trial`` and ``performance_threshold`` and assign a ``label``. Implement the four methods :meth:`instruction_page`, :meth:`trial_maker`, :meth:`trial`, and :meth:`get_stimulus_set`.
The :meth:`instruction_page` method returns an :class:`~psynet.page.InfoPage`, e.g.:

::

    from flask import Markup
    from psynet.page import InfoPage

    def instruction_page(self):
        return InfoPage(Markup(
            """
            <p>We will now perform a test to check your ability to ....</p>
            <p>
                Text for explaining the procedure in more detail.
            </p>
            """
        ), time_estimate=10)


The :meth:`trial_maker` method returns a :class:`~psynet.trial.main.TrialMaker` overriding :meth:`~psynet.trial.main.performance_check`, e.g.:

::
    
    from psynet.trial.non_adaptive import NonAdaptiveTrialMaker

    def trial_maker(
            self,
            time_estimate_per_trial: float,
            performance_threshold: int
        ):
        class SomeNonAdaptivePrescreeningTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                # Calculate values for ``score`` and ``passed``
                return {
                    "score": score,
                    "passed": passed
                }

        return SomeNonAdaptivePrescreeningTrialMaker(
            id_="some_non-adaptive_prescreening_trials",
            trial_class=self.trial(time_estimate_per_trial),
            phase="some_prescreening_phase",
            stimulus_set=self.get_stimulus_set(),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True
        )

The :meth:`trial` method returns a :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial` which implements :meth:`~psynet.trial.main.show_trial` that in turn returns a :class:`~psynet.page.ModularPage` e.g.:

::
    
    from psynet.page import ModularPage
    from psynet.trial.non_adaptive import NonAdaptiveTrial

    def trial(self, time_estimate: float):
        class SomeNonAdaptivePrescreeningTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "some_prescreening_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "some_non-adaptive_prescreening_trial",
                    # Define what is presented to the participant and how participants
                    # may respond utilizing the two principal ``ModularPage``
                    # components ``Prompt`` and ``Control``.
                    #
                    # Prompt(
                    #     "Choose between 1, 2, and 3!"
                    # ),
                    # PushButtonControl(
                    #     ["1", "2", "3"]
                    # ),
                    time_estimate=time_estimate
                )
        return SomeNonAdaptivePrescreeningTrial

The :meth:`get_stimulus_set` method returns a :class:`~psynet.trial.non_adaptive.StimulusSet`,  e.g.:

::

    from psynet.trial.non_adaptive import StimulusSet, StimulusSpec

    def get_stimulus_set(self):
        stimuli = []
        # Construct a list of ``StimulusSpec`` objects and pass it to
        # the ``StimulusSet`` constructor.
        return StimulusSet("some_prescreening_task", stimuli)

For concrete implementations, refer to the source code of the three non-adaptive pre-screening tasks :class:`~psynet.prescreen.ColorVocabularyTest`, :class:`~psynet.prescreen.ColorVocabularyTest`, and :class:`~psynet.prescreen.HeadphoneCheck`.
