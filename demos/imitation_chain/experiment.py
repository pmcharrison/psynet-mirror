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
from dlgr_utils.trial.imitation_chain import (
    ImitationChainTrial,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrialGenerator
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

##########################################################################################
#### Stimuli
##########################################################################################

class FixedDigitInputPage(TextInputPage):
    num_digits = 7

    def format_answer(self, answer, metadata, experiment, participant):
        try:
            pattern = re.compile("^[0-9]*$")
            assert len(answer) == self.num_digits
            assert pattern.match(answer)
            return int(answer)
        except (ValueError, AssertionError):
            return "INVALID_RESPONSE"

    def validate(self, parsed_response, experiment, participant, **kwargs):
        if parsed_response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a 7-digit number.")
        return None

class CustomTrial(ImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    num_pages = 2

    def show_trial(self, experiment, participant):
        page_1 = InfoPage(f"Try to remember this 7-digit number: {self.definition:07d}")
        page_2 = FixedDigitInputPage("number", "What was the number?")

        return [
            page_1, 
            page_2
        ]

class CustomNode(ImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarise_trials(self, trials, participant, experiment):
        return round(mean([trial.answer for trial in trials]))

class CustomSource(ImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return random.randint(0, 9999999)

class CustomTrialGenerator(ImitationChainTrialGenerator):
    trial_timeout_sec = 60
    trial_timeout_check_interval = 30

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    timeline = Timeline(
        CustomTrialGenerator(
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_allotted_per_trial=5,
            chain_type="within",
            num_trials_per_participant=20,
            num_chains_per_participant=4,
            num_chains_per_experiment=None,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="num_participants",
            target_num_participants=10,
            async_update_network=True
        ),
        InfoPage("You finished the experiment!", time_allotted=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
