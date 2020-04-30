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
from . import templates
from dallinger import db

import psynet.experiment

from psynet.timeline import get_template
from psynet.field import claim_field
from psynet.participant import Participant, get_participant
from psynet.timeline import (
    Page,
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional,
    switch,
    FailedValidation
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    SliderPage,
    NAFCPage,
    NumberInputPage
)
from psynet.trial.chain import ChainNetwork
from psynet.trial.gibbs import (
    GibbsNetwork, GibbsTrial, GibbsNode, GibbsSource, GibbsTrialMaker
)

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# import rpdb

TARGETS = ["tree", "rock", "carrot", "banana"]
COLORS = ["red", "green", "blue"]

import os


def get_template(name):
    assert isinstance(name, str)
    data_path = os.path.join('templates', name)
    with open(data_path, encoding='utf-8') as fp:
        template_str = fp.read()
    return template_str


class ColorSliderPage(SliderPage):
    def __init__(
            self,
            label: str,
            prompt: Union[str, Markup],
            selected_idx: int,
            starting_values: List[int],
            reverse_scale: bool,
            time_estimate=None,
            **kwargs
    ):
        assert selected_idx >= 0 and selected_idx < len(COLORS)
        self.prompt = prompt
        self.selected_idx = selected_idx
        self.starting_values = starting_values

        not_selected_idxs = list(range(len(COLORS)))
        not_selected_idxs.remove(selected_idx)
        not_selected_colors = [COLORS[i] for i in not_selected_idxs]
        not_selected_values = [starting_values[i] for i in not_selected_idxs]
        hidden_inputs = dict(zip(not_selected_colors, not_selected_values))
        kwargs['template_arg'] = {
            'hidden_inputs': hidden_inputs,
        }
        super().__init__(
            time_estimate=time_estimate,
            # template_path="templates/color-slider.html",
            template_str=get_template("color-slider.html"),
            label=label,
            prompt=prompt,
            start_value=starting_values[selected_idx],
            min_value=0,
            max_value=255,
            slider_id=COLORS[selected_idx],
            reverse_scale=reverse_scale,
            template_arg={
                'hidden_inputs': hidden_inputs,
            }
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt,
            "selected_idx": self.selected_idx,
            "starting_values": self.starting_values
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

    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True

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
            starting_values=self.initial_vector,
            selected_idx=self.active_index,
            reverse_scale=self.reverse_scale,
            time_estimate=5
        )


class CustomNode(GibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}


class CustomSource(GibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}


trial_maker = GibbsTrialMaker(
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    time_estimate_per_trial=5,
    chain_type="within",  # can be "within" or "across"
    num_trials_per_participant=5,
    num_nodes_per_chain=6, # note that the final node receives no trials
    num_chains_per_participant=1,  # set to None if chain_type="across"
    num_chains_per_experiment=None,  # set to None if chain_type="within"
    trials_per_node=1,
    active_balancing_across_chains=True,
    check_performance_at_end=False,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_participants",
    target_num_participants=10,
    # Uncomment the following two lines if you want to experiment
    # with asynchronous processing.
    # async_post_trial="psynet.demos.gibbs.experiment.async_post_trial",
    # async_post_grow_network="psynet.demos.gibbs.experiment.async_post_grow_network"
)


# The following two functions are only necessary if you want to experiment
# with asynchronous processing.
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

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        trial_maker,
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()
