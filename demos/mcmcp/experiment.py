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
    MCMCPTrial, MCMCPNode, MCMCPSource, MCMCPTrialGenerator
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
    def prompt(self):
        ages = [self.definition[item]["age"] for item in self.definition["order"]]
        occupations = [self.definition[item]["occupation"] for item in self.definition["order"]]
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

    def get_proposal(self, state, experiment, participant):
        occupation = state["occupation"]
        age = state["age"] + random.randint(- SAMPLE_RANGE, SAMPLE_RANGE)
        age = age % (MAX_AGE + 1)
        return {
            "occupation": occupation,
            "age": age
        }

class CustomSource(MCMCPSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
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
            trial_class=CustomTrial,
            node_class=CustomNode, 
            source_class=CustomSource,
            phase="experiment",
            time_allotted_per_trial=5,
            chain_type="within",
            num_trials_per_participant=20,
            num_chains_per_participant=6,
            num_chains_per_experiment=None,
            num_nodes_per_chain=5,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            fail_trials_on_participant_performance_check=True
        ),
        InfoPage("You finished the experiment!", time_allotted=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
