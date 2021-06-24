# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random
import re
from statistics import mean

import psynet.experiment
from psynet.modular_page import ModularPage, Prompt, TextControl, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import FailedValidation, Timeline
from psynet.trial.graph import (
    GraphChainNetwork,
    GraphChainNode,
    GraphChainSource,
    GraphChainTrial,
    GridChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# Stimuli
##########################################################################################


class FixedDigitInputPage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: str,
    ):
        self.num_digits = 7

        super().__init__(
            label,
            Prompt(prompt),
            control=TextControl(
                label,
            ),
        )

    def format_answer(self, raw_answer, **kwargs):
        try:
            pattern = re.compile("^[0-9]*$")
            assert len(raw_answer) == self.num_digits
            assert pattern.match(raw_answer)
            return int(raw_answer)
        except (ValueError, AssertionError):
            return "INVALID_RESPONSE"

    def validate(self, response, **kwargs):
        if response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a 7-digit number.")
        return None


class CustomTrial(GraphChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    num_pages = 2

    def show_trial(self, experiment, participant):
        options = [option["content"] for option in self.definition]
        page_1 = ModularPage(
            "custom_trial",
            Prompt("Choose one of the following 7-digit numbers which you'd like to memorize."),
            PushButtonControl(options)
        )
        # page_1 = InfoPage(f"Try to remember this 7-digit number: {self.definition:07d}")
        page_2 = FixedDigitInputPage("number", "What was the number?")

        return [page_1, page_2]


class CustomNetwork(GraphChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}


class CustomNode(GraphChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarize_trials(self, trials: list, experiment, paricipant):
        return round(mean([trial.answer for trial in trials]))


class CustomSource(GraphChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return random.randint(0, 9999999)

    @staticmethod
    def generate_class_seed():
        return random.randint(0, 9999999)


class CustomTrialMaker(GridChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval = 30


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        CustomTrialMaker(
            id_="graph_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            grid_dimension=2,
            phase="experiment",
            time_estimate_per_trial=5,
            chain_type="across",
            num_iterations_per_chain=5,
            num_trials_per_participant=4,
            num_chains_per_participant=None,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="num_participants",
            target_num_participants=10,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
