# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random
import re
from statistics import mean

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, Prompt, TextControl
from psynet.page import InfoPage, SuccessfulEndPage
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


class FixedDigitInputPage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: str,
        time_estimate: float,
    ):
        self.num_digits = 7

        super().__init__(
            label,
            Prompt(prompt),
            control=TextControl(
                label,
            ),
            time_estimate=time_estimate,
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


class CustomTrial(ImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    num_pages = 3
    accumulate_answers = True

    time_estimate = 5 + 3 + 3

    def show_trial(self, experiment, participant):
        page_1 = InfoPage(
            f"Try to remember this 7-digit number: {self.definition:07d}",
            time_estimate=5,
        )
        page_2 = FixedDigitInputPage("number", "What was the number?", time_estimate=3)
        page_3 = FixedDigitInputPage(
            "number", "Type the number one more time.", time_estimate=3
        )

        return [page_1, page_2, page_3]


class CustomNetwork(ImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}


class CustomNode(ImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarize_trials(self, trials: list, experiment, participant):
        def get_answer(trial):
            # Slices the list to get the answers from the second and third pages, then take the mean
            return mean(trial.answer[1:])

        return round(mean([get_answer(trial) for trial in trials]))


class CustomSource(ImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        return random.randint(0, 9999999)


class CustomTrialMaker(ImitationChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval_sec = 30


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        InfoPage(
            """
            We will demonstrate a particular form of the imitation chain experiment where each
            'show_trial' comprises multiple pages. This allows you to ask the participant the same
            question multiple times in a row. This is occasionally useful in production experiments.
            """,
            time_estimate=3,
        ),
        CustomTrialMaker(
            id_="imitation_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            chain_type="within",
            num_iterations_per_chain=5,
            num_trials_per_participant=5,
            num_chains_per_participant=1,
            num_chains_per_experiment=None,
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
