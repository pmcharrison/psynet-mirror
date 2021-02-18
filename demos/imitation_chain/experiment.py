# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random
import re
from statistics import mean

import psynet.experiment
from psynet.page import InfoPage, SuccessfulEndPage, TextInputPage
from psynet.timeline import FailedValidation, Timeline
from psynet.trial.imitation_chain import (
    ImitationChainNetwork,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# Stimuli
##########################################################################################


class FixedDigitInputPage(TextInputPage):
    num_digits = 7

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


class CustomTrial(ImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    num_pages = 2

    def show_trial(self, experiment, participant):
        page_1 = InfoPage(f"Try to remember this 7-digit number: {self.definition:07d}")
        page_2 = FixedDigitInputPage("number", "What was the number?")

        return [page_1, page_2]


class CustomNetwork(ImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}


class CustomNode(ImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarise_trials(self, trials: list, experiment, paricipant):
        return round(mean([trial.answer for trial in trials]))


class CustomSource(ImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return random.randint(0, 9999999)


class CustomTrialMaker(ImitationChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval = 30


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        CustomTrialMaker(
            id_="imitation_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_estimate_per_trial=5,
            chain_type="within",
            num_nodes_per_chain=5,
            num_trials_per_participant=5,
            num_chains_per_participant=1,
            num_chains_per_experiment=None,
            trials_per_node=1,
            active_balancing_across_chains=True,
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


extra_routes = Exp().extra_routes()
