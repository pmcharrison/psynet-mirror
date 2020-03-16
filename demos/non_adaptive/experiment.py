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
    ReactivePage, 
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
        phase="experiment"
    )
    for animal in ["cats", "dogs", "fish", "ponies"]
])

class AnimalTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "animal_trial"}

    def show_trial(self, experiment, participant):
        text_color = self.definition["text_color"]
        animal = self.definition["animal"]
        
        return NAFCPage(
            "animal_trial", 
            Markup(f"<p style='color: {text_color}'>How much do you like {animal}?</p>"),
            ["Not at all", "A little", "Very much"]
        )

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        NonAdaptiveTrialGenerator(
            AnimalTrial, 
            phase="experiment",
            stimulus_set=stimulus_set, 
            time_allotted_per_trial=3,
            expected_num_trials=stimulus_set.estimate_num_trials_per_participant(),
            new_participant_group=True
        ),
        InfoPage("You finished the animal questions!", time_allotted=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
