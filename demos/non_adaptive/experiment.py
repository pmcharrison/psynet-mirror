# pylint: disable=unused-import,abstract-method

##########################################################################################
#### Imports
##########################################################################################

import logging

from flask import Markup

import psynet.experiment
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.non_adaptive import (
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

import rpdb

##########################################################################################
#### Stimuli
##########################################################################################

stimulus_set = StimulusSet(
    "animals",
    [
        StimulusSpec(
            definition={"animal": animal},
            version_specs=[
                StimulusVersionSpec(definition={"text_color": text_color})
                for text_color in ["red", "green", "blue"]
            ],
            phase="experiment",
            block=block,
        )
        for animal in ["cats", "dogs", "fish", "ponies"]
        for block in ["A", "B", "C"]
    ],
)


class AnimalTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "animal_trial"}

    # num_pages = 2

    def show_trial(self, experiment, participant):
        text_color = self.definition["text_color"]
        animal = self.definition["animal"]
        block = self.block

        header = f"<h4 id='trial-position'>Trial {self.position + 1}</h3>"

        if self.is_repeat_trial:
            header = (
                header
                + f"<h4>Repeat trial {self.repeat_trial_index + 1} out of {self.num_repeat_trials}</h3>"
            )
        else:
            header = header + f"<h4>Block {block}</h3>"

        page = ModularPage(
            "animal_trial",
            Markup(
                f"""
                {header}
                <p style='color: {text_color}'>How much do you like {animal}?</p>
                """
            ),
            PushButtonControl(["Not at all", "A little", "Very much"]),
        )

        return page

    # def show_feedback(self, experiment, participant):
    #     return InfoPage(f"You responded '{self.answer}'.")


class AnimalTrialMaker(NonAdaptiveTrialMaker):
    def performance_check(self, experiment, participant, participant_trials):
        """Should return a tuple (score: float, passed: bool)"""
        score = 0
        for trial in participant_trials:
            if trial.answer == "Not at all":
                score += 1
        passed = score == 0
        return {"score": score, "passed": passed}

    give_end_feedback_passed = True

    def get_end_feedback_passed_page(self, score):
        return InfoPage(
            Markup(f"You finished the animal questions! Your score was {score}."),
            time_estimate=5,
        )


trial_maker = AnimalTrialMaker(
    id_="animals",
    trial_class=AnimalTrial,
    phase="experiment",
    stimulus_set=stimulus_set,
    time_estimate_per_trial=3,
    max_trials_per_block=2,
    allow_repeated_stimuli=True,
    max_unique_stimuli_per_block=None,
    active_balancing_within_participants=True,
    active_balancing_across_participants=True,
    check_performance_at_end=True,
    check_performance_every_trial=True,
    target_num_participants=1,
    target_num_trials_per_stimulus=None,
    recruit_mode="num_participants",
    num_repeat_trials=3,
)

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(trial_maker, SuccessfulEndPage())

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()
