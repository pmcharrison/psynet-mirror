# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random

import psynet.experiment
from psynet.page import InfoPage, NAFCPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.mcmcp import (
    MCMCPNetwork,
    MCMCPNode,
    MCMCPSource,
    MCMCPTrial,
    MCMCPTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# Stimuli
##########################################################################################

MAX_AGE = 100
OCCUPATIONS = ["doctor", "babysitter", "teacher"]
SAMPLE_RANGE = 5


class CustomNetwork(MCMCPNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    def make_definition(self):
        return {"occupation": self.balance_across_networks(OCCUPATIONS)}


class CustomSource(MCMCPSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return {"age": random.randint(0, MAX_AGE)}


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
    consent_audiovisual_recordings = False

    timeline = Timeline(
        MCMCPTrialMaker(
            id_="mcmcp_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",  # can be whatever you like
            time_estimate_per_trial=5,
            chain_type="across",  # can be "within" or "across"
            num_trials_per_participant=10,
            num_chains_per_participant=None,  # set to None if chain_type="across"
            num_chains_per_experiment=10,  # set to None if chain_type="within"
            num_iterations_per_chain=2,
            trials_per_node=1,
            active_balancing_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            fail_trials_on_participant_performance_check=True,
            recruit_mode="num_trials",
            target_num_participants=None,
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


extra_routes = Exp().extra_routes()
