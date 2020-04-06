# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
import random
import re
from typing import Union, List
import time

from dallinger import db

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
    ResponsePage
)
from dlgr_utils.page import (
    InfoPage, 
    SuccessfulEndPage, 
    NAFCPage, 
    NumberInputPage
)
from dlgr_utils.trial.chain import ChainNetwork
from dlgr_utils.trial.gibbs import (
    GibbsNetwork, GibbsTrial, GibbsNode, GibbsSource, GibbsTrialMaker
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

TARGETS = ["tree", "rock", "carrot", "banana"]
COLORS = ["red", "green", "blue"]

class ColorSliderPage(ResponsePage): 
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        selected: str,   
        starting_values: List[int],
        time_estimate=None
    ):
        assert selected in ["red", "green", "blue"]
        self.prompt = prompt
        self.selected = selected
        self.starting_values = starting_values

        super().__init__(
            time_estimate=time_estimate,
            template_path="templates/color-slider.html",
            label=label,
            template_arg={
                "prompt": prompt,
                "selected": selected,
                "red": starting_values[0],
                "green": starting_values[1],
                "blue": starting_values[2]
            }
        )
    def compile_details(self, response, answer, metadata, experiment, participant):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt,
            "selected": self.selected,
            "initial_values": self.starting_values
        }

class CustomNetwork(GibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}
    
    vector_length = 3
    
    def random_sample(self, i):
        return random.randint(0, 255)
    
    def make_definition(self):
        return {
            "target": self.balance_across_networks(TARGETS)
        }

class CustomTrial(GibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        selected_color = COLORS[self.active_index]
        target = self.network.definition["target"]
        prompt = Markup(
            "Adjust the slider to match the following word as well as possible: "
            f"<strong>{target}</strong>"
        )
        return ColorSliderPage(
            "color_trial",
            prompt,
            selected=selected_color,
            starting_values=self.initial_vector,
            time_estimate=5
        )

class CustomNode(GibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

class CustomSource(GibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

trial_maker = GibbsTrialMaker(
    network_class=GibbsNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode, 
    source_class=CustomSource,
    phase="experiment",
    time_estimate_per_trial=5,
    chain_type="within",
    num_trials_per_participant=20,
    num_nodes_per_chain=5,
    num_chains_per_participant=5,
    num_chains_per_experiment=None,
    trials_per_node=1,
    active_balancing_across_chains=True,
    check_performance_at_end=False,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="test",
    target_num_participants=10,
    async_post_trial="dlgr_utils.demos.gibbs_sampler.experiment.async_post_trial",
    async_post_grow_network="dlgr_utils.demos.gibbs_sampler.experiment.async_post_grow_network"
)

def async_post_trial(trial_id):
    logger.info("Running async_post_trial for trial %i...", trial_id)
    trial = CustomTrial.query.filter_by(id=trial_id).one()
    time.sleep(1000)
    trial.awaiting_process = False
    db.session.commit()

def async_post_grow_network(network_id):
    logger.info("Running async_post_grow_network for network %i...", network_id)
    network = ChainNetwork.query.filter_by(id=network_id).one()
    time.sleep(0)
    network.awaiting_process = False
    db.session.commit()

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        trial_maker,
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
