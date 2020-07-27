# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### About
##########################################################################################

# This is a version of the Gibbs demo that introduces failing of asynchronous
# processes on various nodes and trials. It is intended to demonstrate the
# pruning processes by which PsyNet copes with these failures. Try taking the experiment
# as a few participants then inspecting the monitor route.

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
from psynet.utils import get_logger

logger = get_logger()

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

    # Minimal example of an async_post_grow_network function
    run_async_post_grow_network = True
    def async_post_grow_network(self):
        logger.info("Running custom async_post_grow_network function (network id = %i)", self.id)
        if self.num_nodes > 1:
            if self.head.id % 3 == 0:
                assert False
            elif self.head.id % 4 == 0:
                import time
                time.sleep(1e6)

class CustomTrial(GibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True

    def show_trial(self, experiment, participant):
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

    def show_feedback(self, experiment, participant):
        if self.failed:
            prompt = "Trial failed."
        else:
            prompt = "Trial was successful."

        return InfoPage(prompt, time_estimate=5)

    # Minimal example of an async_post_trial function
    run_async_post_trial = True
    def async_post_trial(self):
        logger.info("Running custom async post trial (id = %i)", self.id)
        if self.id % 3 == 0:
            assert False
        elif self.id % 4 == 0:
            import time
            time.sleep(1e6)

class CustomNode(GibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}


class CustomSource(GibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

class CustomTrialMaker(GibbsTrialMaker):
    give_end_feedback_passed = True
    performance_threshold = -1.0
    async_timeout_sec = 5
    check_timeout_interval = 5

    def get_end_feedback_passed_page(self, score):
        score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

        return InfoPage(
            Markup(f"Your consistency score was <strong>{score_to_display}&#37;</strong>."),
            time_estimate=5
        )


trial_maker = CustomTrialMaker(
    id_="async_pruning",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    source_class=CustomSource,
    phase="experiment",  # can be whatever you like
    time_estimate_per_trial=5,
    chain_type="across",  # can be "within" or "across"
    num_trials_per_participant=4,
    num_iterations_per_chain=5, # note that the final node receives no trials
    num_chains_per_participant=None,  # set to None if chain_type="across"
    num_chains_per_experiment=4,  # set to None if chain_type="within"
    trials_per_node=1,
    active_balancing_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="num_participants",
    target_num_participants=10
)

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        trial_maker,
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()
