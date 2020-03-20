# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
import random
import re

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
    switch,
    FailedValidation,
    TextInputPage
)
from dlgr_utils.trial.mcmcp import (
    MCMCPTrialGenerator, MCMCPTrial, MCMCPNode, MCMCPSource
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

MAX_AGE = 100
OCCUPATIONS = ["doctor", "babysitter", "teacher"]
SAMPLE_RANGE = 5
NUM_CHOICES = 2

class CustomTrial(MCMCPTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    @property
    def get_prompt(self):
        ages = [self.definition[item]["age"] for item in self.order]
        occupations = [self.definition[item]["occupation"] for item in self.order]
        assert len(set(occupations)) == 1
        occupation = occupations[0]
        
        return(
            f"Person A is {ages[0]} years old. "
            f"Person B is {ages[1]} years old. "
            f"Which one is the {occupation}?"
        )

    def show_trial(self, experiment, participant):
        return NAFCPage(
            "mcmcp_trial",
            self.prompt,
            choices=["0", "1"], 
            time_allotted=5,
            labels=["Person A", "Person B"],
        )

class CustomNode(MCMCPNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def get_proposal(self, state, network, experiment, partipant):
        occupation = self.current_state["occupation"]
        age = self.current_state["age"] + random.randint(- SAMPLE_RANGE, SAMPLE_RANGE)
        age = age % (MAX_AGE + 1)
        return {
            "occupation": occupation,
            "age": age
        }

class CustomSource(CustomNode, MCMCPSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_initial_state(self, network, experiment, participant):
        return {
            "occupation": self.occupation,
            "age": self.sample_age()
        }

    @property
    def occupation(self):
        network = self.network
        if network.chain_type == "across":
            index = network.id
        elif network.chain_type == "within":
            index = network.id_within_participant
        else:
            raise ValueError(f"Unidentified chain type: {network.chain_type}")
        return OCCUPATIONS[index % len(OCCUPATIONS)]
    
    @staticmethod
    def sample_age():
        return random.randint(0, MAX_AGE)


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        MCMCPTrialGenerator(
            source_class=CustomSource,
            trial_class=Trial, 
            phase="experiment",
            time_allotted_per_trial=5,
            chain_type="within",
            num_trials_per_participant=20,
            num_chains_per_participant=4,
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
