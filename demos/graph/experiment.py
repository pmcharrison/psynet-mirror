# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random
import re
from statistics import mean
from typing import Optional, Union
from flask import Markup
import rpdb

import psynet.experiment
from psynet.modular_page import ModularPage, Prompt, TextControl, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import FailedValidation, Timeline
from psynet.trial.graph import (
    GraphChainNetwork,
    GraphChainNode,
    GraphChainSource,
    GraphChainTrial,
    GraphChainTrialMaker,
)
from psynet.consent import MTurkStandardConsent
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

    # def generate_seed(self, network, experiment, participant):
    #     return random.randint(1000000, 9999999)

    @staticmethod
    def generate_class_seed():
        return random.randint(1000000, 9999999)


class CustomTrialMaker(GraphChainTrialMaker):
    """
    This TrialMaker implements a square lattice graph of dimensions grid_dimension x grid_dimension
    """

    response_timeout_sec = 60
    check_timeout_interval = 30

    def __init__(
        self,
        *,
        id_,
        network_class,
        node_class,
        source_class,
        trial_class,
        phase: str,
        time_estimate_per_trial: Union[int, float],
        grid_dimension: int,
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_num_participants=Optional[int],
        num_iterations_per_chain: Optional[int] = None,
        num_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        num_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):

        network_structure = self.generate_grid(grid_dimension)
        super().__init__(
            id_=id_,
            network_class=network_class,
            node_class=node_class,
            source_class=source_class,
            trial_class=trial_class,
            phase=phase,
            time_estimate_per_trial=time_estimate_per_trial,
            network_structure=network_structure,
            chain_type=chain_type,
            num_trials_per_participant=num_trials_per_participant,
            num_chains_per_participant=num_chains_per_participant,
            trials_per_node=trials_per_node,
            balance_across_chains=balance_across_chains,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_iterations_per_chain=num_iterations_per_chain,
            num_nodes_per_chain=num_nodes_per_chain,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=wait_for_networks,
            allow_revisiting_networks_in_across_chains=allow_revisiting_networks_in_across_chains
        )

    def generate_grid(self, size):
        vertices = [i for i in range(1, size**2 + 1)]
        edges = []
        for v in vertices:
            if v % size != 0:
                edges = edges + [{"origin": v, "target": v + 1, "properties": {"type": "default"}}]
            if (v - 1) % size != 0:
                edges = edges + [{"origin": v, "target": v - 1, "properties": {"type": "default"}}]
            if (v + size) <= size ** 2:
                edges = edges + [{"origin": v, "target": v + size, "properties": {"type": "default"}}]
            if (v - size) > 0:
                edges = edges + [{"origin": v, "target": v - size, "properties": {"type": "default"}}]
        return {"vertices": vertices, "edges": edges}

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        MTurkStandardConsent(),
        InfoPage(Markup("""
            <p>
            This experiment implements a simple task on a square lattice.
            This is done by specifying an approppriate dictionary of edges and vertices which in
            turn is passed to <code>GraphChainTrialMaker</code> through <code>network_structure</code>.
            The dictionary should take the following form:
            </p>
            <code>
            {
                "vertices": [1,2],
                "edges": [{"origin": 1, "target": 2, "properties": {"type": "default"}}]
            }
            </code>
        """), time_estimate=10),
        InfoPage(Markup("""
            The task itself consists of choosing a stimulus from one of your neighbours
            on the lattice and replicating it.
        """), time_estimate=5),
        InfoPage("Let's begin!", time_estimate=3),
        CustomTrialMaker(
            id_="graph_demo",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            grid_dimension=3,
            phase="experiment",
            time_estimate_per_trial=5,
            chain_type="across",
            num_iterations_per_chain=5,
            num_trials_per_participant=9,
            num_chains_per_participant=None,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="num_trials",
            target_num_participants=None,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
