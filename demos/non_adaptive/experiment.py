# pylint: disable=unused-import,abstract-method

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup

import dlgr_utils.experiment
from dlgr_utils.field import claim_field
from dlgr_utils.participant import Participant, get_participant
from dlgr_utils.timeline import (
    Page, 
    InfoPage, 
    Timeline,
    SuccessfulEndPage, 
    PageMaker, 
    NAFCPage, 
    CodeBlock, 
    while_loop, 
    conditional, 
    switch
)
from dlgr_utils.trial.non_adaptive import (
    NonAdaptiveTrialGenerator,
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

        page = NAFCPage(
            "animal_trial", 
            Markup(f"<h3>Block {block}</h3> <p style='color: {text_color}'>How much do you like {animal}?</p>"),
            ["Not at all", "A little", "Very much"]
        )

        return page

    # def show_feedback(self, experiment, participant):
    #     return InfoPage(f"You responded '{self.answer}'.")

class AnimalTrialGenerator(NonAdaptiveTrialGenerator):
    def performance_check(self, experiment, participant, participant_trials):
        """Should return a tuple (score: float, passed: bool)"""
        score = 0
        for trial in participant_trials:
            if trial.answer == "Not at all":
                score +=1
        passed = score == 0
        return (score, passed)


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        AnimalTrialGenerator(
            AnimalTrial, 
            phase="experiment",
            stimulus_set=stimulus_set, 
            time_allotted_per_trial=3,
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
            recruit_mode="num_trials"
        ),
        InfoPage("You finished the animal questions!", time_allotted=0),
        CodeBlock(lambda experiment: experiment.recruit()), # only for local testing, delete on online deployment
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 2

extra_routes = Exp().extra_routes()
