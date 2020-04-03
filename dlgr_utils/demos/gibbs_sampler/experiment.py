# pylint: disable=unused-import,abstract-method,unused-argument

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
    InfoPage, 
    Timeline,
    SuccessfulEndPage, 
    PageMaker, 
    NAFCPage, 
    CodeBlock, 
    NumberInputPage,
    while_loop, 
    conditional, 
    switch,
    FailedValidation,
    ResponsePage
)
from dlgr_utils.trial.chain import ChainNetwork
from dlgr_utils.trial.gibbs_sampler import (
    GibbsTrial, GibbsNode, GibbsSource, GibbsTrialGenerator
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
        time_allotted=None
    ):
        assert selected in ["red", "green", "blue"]
        self.prompt = prompt
        self.selected = selected
        self.starting_values = starting_values

        super().__init__(
            time_allotted=time_allotted,
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

class CustomTrial(GibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    @property 
    def target(self):
        return self.source.target

    @property
    def prompt(self):
        return(Markup(
            "Adjust the slider to match the following word as well as possible: "
            f"<strong>{self.target}</strong>"
        ))

    def show_trial(self, experiment, participant):
        selected_color = COLORS[self.active_index]

        return ColorSliderPage(
            "color_trial",
            self.prompt,
            selected=selected_color,
            starting_values=self.initial_vector,
            time_allotted=5
        )

class CustomNode(GibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

class CustomSource(GibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return {
            "active_index": random.randint(0, 2),
            "vector": [random.randint(0, 255) for _ in COLORS]
        }

    @property
    def target(self):
        network = self.network
        if network.chain_type == "across":
            index = network.id
        elif network.chain_type == "within":
            index = network.id_within_participant
        else:
            raise ValueError(f"Unidentified chain type: {network.chain_type}")
        return TARGETS[index % len(TARGETS)]

trial_generator = GibbsTrialGenerator(
    trial_class=CustomTrial,
    node_class=CustomNode, 
    source_class=CustomSource,
    phase="experiment",
    time_allotted_per_trial=5,
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
        trial_generator,
        InfoPage("You finished the experiment!", time_allotted=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
