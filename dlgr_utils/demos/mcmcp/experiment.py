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
    Timeline,
    PageMaker, 
    CodeBlock, 
    while_loop, 
    conditional, 
    switch,
    FailedValidation,
)
from dlgr_utils.page import (
    InfoPage, 
    SuccessfulEndPage, 
    NAFCPage, 
    NumberInputPage,
    TextInputPage
)
from dlgr_utils.trial.mcmcp import (
    MCMCPNetwork, MCMCPTrial, MCMCPNode, MCMCPSource, MCMCPTrialMaker
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

class CustomNetwork(MCMCPNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}
    
    def make_definition(self):
        return {
            "occupation": self.balance_across_networks(OCCUPATIONS)
        }

class CustomSource(MCMCPSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return {
            "age": random.randint(0, MAX_AGE)
        }
        
class CustomTrial(MCMCPTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        occupation = self.network.definition["occupation"]
        age_1 = self.first_stimulus["age"]
        age_2 = self.second_stimulus["age"]
        prompt = (
            f"Person A is {age_1} years old. "
            f"Person B is {age_2} years old. "
            f"Which one is the {occupation}?"
        )
        return NAFCPage(
            "mcmcp_trial",
            prompt,
            choices=["0", "1"], 
            time_estimate=5,
            labels=["Person A", "Person B"],
        )

class CustomNode(MCMCPNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def get_proposal(self, state, experiment, participant):
        age = state["age"] + random.randint(- SAMPLE_RANGE, SAMPLE_RANGE)
        age = age % (MAX_AGE + 1)
        return {
            "age": age
        }

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        MCMCPTrialMaker(
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode, 
            source_class=CustomSource,
            phase="experiment", # can be whatever you like
            time_estimate_per_trial=5,
            chain_type="within", # can be "within" or "across"
            num_trials_per_participant=10,
            num_chains_per_participant=1, # set to None if chain_type="across"
            num_chains_per_experiment=None, # set to None if chain_type="within"
            num_nodes_per_chain=10,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            fail_trials_on_participant_performance_check=True,
            recruit_mode="num_participants",
            target_num_participants=10
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        # CodeBlock(lambda experiment: experiment.recruit()), # only for local testing, delete on online deployment
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1 # increase to simulate multiple participants at once

extra_routes = Exp().extra_routes()
