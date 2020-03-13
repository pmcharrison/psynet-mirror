# pylint: disable=unused-import

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
from dlgr_utils.trial.main import Trial
from dlgr_utils.trial.non_adaptive import (
    NonAdaptiveTrialGenerator,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from datetime import datetime

stimulus_set = StimulusSet([
    StimulusSpec(
        definition={"animal": animal},
        version_specs=[
            StimulusVersionSpec(
                definition={"text_colour": text_colour}
            )
            for text_colour in ["red", "green", "blue"]
        ],
        phase="experiment"
    )
    for animal in ["cat", "dog", "fish", "pony"]
])

class AnimalTrial(Trial):
    def show_trial(self, experiment, participant):
        

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    # pylint: disable=abstract-method
    timeline = Timeline(
        InfoPage("Hello!", time_allotted=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
