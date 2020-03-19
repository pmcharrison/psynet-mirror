# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
from random import random

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
    NumberInputPage,
    while_loop, 
    conditional, 
    switch
)
from dlgr_utils.trial.imitation_chain import (
    ImitationChainTrialGenerator, ImitationChainTrial
)
from dlgr_utils.trial.chain import(
    ChainTrial,
    ChainSource
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

##########################################################################################
#### Stimuli
##########################################################################################

class Trial(ImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    num_pages = 2

    def show_trial(self, experiment, participant):
        page_1 = InfoPage(f"Try to remember this number: {self.definition}")
        page_2 = NumberInputPage("number", "What was the number?")

        return [
            page_1, 
            page_2
        ]

class TrialGenerator(ImitationChainTrialGenerator):
    def summarise_answers(self, trials, participant, experiment):
        return mean([trial.answer for trial in trials])

class Source(ChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_definition(self, network, experiment, participant):
        return random()

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        TrialGenerator(
            source_class=Source,
            trial_class=Trial, 
            phase="experiment",
            time_allotted_per_trial=5,
            chain_type="within",
            num_trials_per_participant=9,
            num_chains_per_participant=3,
            num_chains_per_experiment=None,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False
        ),
        InfoPage("You finished the experiment!", time_allotted=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
