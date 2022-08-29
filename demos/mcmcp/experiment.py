# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random

import psynet.experiment
from psynet.consent import MainConsent
from psynet.modular_page import PushButtonControl
from psynet.page import InfoPage, ModularPage, Prompt, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.mcmcp import MCMCPNetwork, MCMCPNode, MCMCPTrial, MCMCPTrialMaker
from psynet.utils import get_logger

logger = get_logger()

from .test_imports import CustomCls  # noqa -- this is to test custom class import

##########################################################################################
# Stimuli
##########################################################################################

MAX_AGE = 100
OCCUPATIONS = ["doctor", "babysitter", "teacher"]
SAMPLE_RANGE = 5


class CustomNetwork(MCMCPNetwork):
    def make_definition(self):
        return {"occupation": self.balance_across_networks(OCCUPATIONS)}


class CustomTrial(MCMCPTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        occupation = self.network.definition["occupation"]
        age_1 = self.first_stimulus["age"]
        age_2 = self.second_stimulus["age"]
        prompt = (
            f"Person A is {age_1} years old. "
            f"Person B is {age_2} years old. "
            f"Which one is the {occupation}?"
        )
        return ModularPage(
            "mcmcp_trial",
            Prompt(prompt),
            control=PushButtonControl(
                ["0", "1"], labels=["Person A", "Person B"], arrange_vertically=False
            ),
            time_estimate=self.time_estimate,
        )


class CustomNode(MCMCPNode):
    def create_initial_seed(self, experiment, participant):
        return {"age": random.randint(0, MAX_AGE)}

    def get_proposal(self, state, experiment, participant):
        age = state["age"] + random.randint(-SAMPLE_RANGE, SAMPLE_RANGE)
        age = age % (MAX_AGE + 1)
        return {"age": age}


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "MCMCP demo experiment"

    variables = {
        "show_abort_button": True,
    }

    timeline = Timeline(
        MainConsent(),
        MCMCPTrialMaker(
            id_="mcmcp_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            chain_type="within",  # can be "within" or "across"
            num_trials_per_participant=10,
            num_chains_per_participant=2,  # set to None if chain_type="across"
            num_chains_per_experiment=None,  # set to None if chain_type="within"
            num_iterations_per_chain=6,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            fail_trials_on_participant_performance_check=True,
            recruit_mode="num_participants",
            target_num_participants=1,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        # CodeBlock(lambda experiment: experiment.recruit()), # only for local testing, delete on online deployment
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = (
            1  # increase to simulate multiple participants at once
        )
