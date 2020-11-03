# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
from statistics import mean
import random
import re
import json
from uuid import uuid4

import psynet.experiment
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
    NAFCPage,
    NumberInputPage,
    TextInputPage,
    UnityPage,
)
from psynet.trial.imitation_chain import (
    ImitationChainTrial,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrialMaker,
    ImitationChainNetwork
)

from psynet.utils import get_logger
logger = get_logger()

import rpdb

##########################################################################################
#### Stimuli
##########################################################################################

# class FixedDigitInputPage(TextInputPage):
#     num_digits = 7

#     def format_answer(self, raw_answer, **kwargs):
#         try:
#             pattern = re.compile("^[0-9]*$")
#             assert len(raw_answer) == self.num_digits
#             assert pattern.match(raw_answer)
#             return int(raw_answer)
#         except (ValueError, AssertionError):
#             return "INVALID_RESPONSE"

    # def validate(self, response, **kwargs):
    #     if response.answer == "INVALID_RESPONSE":
    #         return FailedValidation("Please enter a 7-digit number.")
    #     return None

class CustomUnityPage(UnityPage):
    def format_answer(self, raw_answer, **kwargs):
        return int(json.loads(raw_answer)["result"])


class CustomTrial(ImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    session_id = str(uuid4())
    num_pages = 2

    def show_trial(self, experiment, participant):
        page_1 = InfoPage("Welcome to the Unity imitation chain experiment")
        page_2 = CustomUnityPage(
            title="Unity imitation chain experiment",
            game_container_width="960px",
            game_container_height="600px",
            contents=self.definition,
            participant=self.participant,
            resources="/static",
            time_estimate=5,
            session_id=self.session_id,
        )
        # page_3 = CustomUnityPage(
        #     title="Unity imitation chain experiment",
        #     game_container_width="960px",
        #     game_container_height="600px",
        #     contents=99,
        #     resources="/static",
        #     time_estimate=5,
        #     session_id = session_id,
        # )

        return [
            page_1,
            page_2
        ]

class CustomNetwork(ImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

class CustomNode(ImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarise_trials(self, trials: list, experiment, paricipant):
        logger.info(trials)
        logger.info(trials[0])
        logger.info(trials[0].answer)
        return round(mean([trial.answer for trial in trials]))

class CustomSource(ImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        #val=(network.id %90) +10
        list_of_networks=[0,10,20,50,100]
        val=list_of_networks[ network.id % len(list_of_networks) ]
        return val
        #return val #random.randint(10, 90)

class CustomTrialMaker(ImitationChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval = 30

    def compute_bonus(self, score, passed):
            if score is None:
                return 0.1 # give base pay
            else:
                return max(2.0, score)

    # def performance_check(self, experiment, participant, participant_trials):
    #     """Should return a tuple (bonus: float, passed: bool)"""
    #     bonus = 0
    #     for trial in participant_trials:
    #         bonus += json.loads(trial.raw_answer)["bonus"]
    #     passed = bonus == 0
    #     return {
    #         "bonus": bonus,
    #         "passed": passed
    #     }

##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        CustomTrialMaker(
            id_="imitation_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_estimate_per_trial=60,
            chain_type="within",
            num_nodes_per_chain=5,
            num_trials_per_participant=1,
            num_chains_per_participant=1,
            num_chains_per_experiment=None,
            trials_per_node=10,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="num_participants",
            target_num_participants=10
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

extra_routes = Exp().extra_routes()
