# pylint: disable=unused-import,abstract-method

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup

import psynet.experiment
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import (
    Page,
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional,
    switch
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    NAFCPage
)
from psynet.trial.non_adaptive import (
    NonAdaptiveTrialMaker,
    NonAdaptiveTrial,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

##########################################################################################
#### Stimuli
##########################################################################################

stimulus_set = StimulusSet([
    StimulusSpec(
        definition={"animal": animal},
        version_specs=[
            StimulusVersionSpec(
                definition={"text_color": text_color}
            )
            for text_color in ["red", "green", "blue"]
        ],
        phase="experiment",
        block=block
    )
    for animal in ["cats", "dogs", "fish", "ponies"]
    for block in ["A", "B", "C"]
])

class AnimalTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "animal_trial"}

    # num_pages = 2

    def show_trial(self, experiment, participant):
        text_color = self.definition["text_color"]
        animal = self.definition["animal"]
        block = self.block

        if self.is_repeat_trial:
            header = f"<h3>Repeat trial {self.repeat_trial_index + 1} out of {self.num_repeat_trials}</h3>"
        else:
            header = f"<h3>Block {block}</h3>"

        page = NAFCPage(
            "animal_trial",
            Markup(
                f"""
                {header}
                <p style='color: {text_color}'>How much do you like {animal}?</p>
                """),
            ["Not at all", "A little", "Very much"]
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
                score +=1
        passed = score == 0
        return {
            "score": score,
            "passed": passed,
            "bonus": 0.0
        }

    give_end_feedback_passed = True
    def get_end_feedback_passed_page(self, score):
        return InfoPage(
            Markup(f"You finished the animal questions! Your score was {score}."),
            time_estimate=5
        )


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        AnimalTrialMaker(
            trial_class=AnimalTrial,
            phase="experiment",
            stimulus_set=stimulus_set,
            time_estimate_per_trial=3,
            new_participant_group=True,
            max_trials_per_block=2,
            allow_repeated_stimuli=True,
            max_unique_stimuli_per_block=None,
            active_balancing_within_participants=True,
            active_balancing_across_participants=True,
            check_performance_at_end=True,
            check_performance_every_trial=True,
            target_num_participants=None,
            target_num_trials_per_stimulus=3,
            recruit_mode="num_trials",
            num_repeat_trials=3
        ),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
