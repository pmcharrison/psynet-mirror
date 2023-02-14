# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################
import json
from random import sample

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import Control, ModularPage, Prompt
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial import ChainNode
from psynet.trial.create_and_rate import (
    CREATOR_KEY,
    ROLE_KEY,
    CreateAndRateNode,
    CreateAndRateTrial,
    CreateAndRateTrialMaker,
)
from psynet.trial.imitation_chain import ImitationChainTrial, ImitationChainTrialMaker
from psynet.utils import get_logger

from .utils import final_questionnaire, instructions

logger = get_logger()

with open("data.json") as f:
    dummy_data = json.load(f)


CREATE_TRIALS = 2
RATE_TRIALS = 2
N_REPEAT_ITEMS = 0
NUM_ITERATIONS = 1
VISITED_RULE_IDS_KEY = "visited_rule_ids"
MAX_TIME = 60 * 5  # 5 minutes
AVG_TIME_ESTIMATE = 20


class CreatorPrompt(Prompt):
    macro = "creator_prompt"
    external_template = "custom-macros.html"

    def __init__(
        self,
        positive_examples: list,
        negative_examples: list,
        predicted_rules: list,
        node_id: int,
        rule: str,
    ):
        super().__init__()
        self.positive_examples = positive_examples
        self.negative_examples = negative_examples
        self.predicted_rules = predicted_rules
        self.node_id = node_id
        self.rule = rule

    @property
    def metadata(self):
        return {
            "positive_examples": self.positive_examples,
            "negative_examples": self.negative_examples,
            "predicted_rules": self.predicted_rules,
            "node_id": self.node_id,
            "rule": self.rule,
        }


class CreatorControl(Control):
    macro = "creator_control"
    external_template = "custom-macros.html"

    def get_bot_response(self, experiment, bot, page, prompt):
        context = prompt.metadata
        node_id = context["node_id"]
        node = [node for node in CreateAndRateNode.query.all() if node.id == node_id][0]

        non_failed_creations = get_non_failed_creations(node)
        gpt3_rules = prompt.metadata["predicted_rules"]
        if len(non_failed_creations) < len(gpt3_rules):
            return {"rule": gpt3_rules[len(non_failed_creations)]}


class RaterPrompt(CreatorPrompt):
    macro = "rater_prompt"
    external_template = "custom-macros.html"


class RaterControl(Control):
    macro = "rater_control"
    external_template = "custom-macros.html"


class CustomTrial(ImitationChainTrial, CreateAndRateTrial):
    time_estimate = AVG_TIME_ESTIMATE

    def _get_prompt_args(self):
        context = self.node.context
        predicted_rules = [
            t.answer["rule"] for t in get_non_failed_creations(self.node)
        ]
        return (
            context["positives"],
            context["negatives"],
            predicted_rules,
            self.node.id,
            context["rule"],
        )

    def show_create_trial(self, experiment, participant):
        return ModularPage(
            "create_trial",
            CreatorPrompt(*self._get_prompt_args()),
            CreatorControl(),
            time_estimate=self.time_estimate,
        )

    def show_rate_trial(self, experiment, participant):
        positives, negatives, predicted_rules, node_id, rule = self._get_prompt_args()
        predicted_rules = sample(predicted_rules, len(predicted_rules))
        predicted_rules += sample(predicted_rules, N_REPEAT_ITEMS)
        return ModularPage(
            "rate_trial",
            RaterPrompt(positives, negatives, predicted_rules, node_id, rule),
            RaterControl(),
            time_estimate=self.time_estimate,
        )

    def show_trial(self, experiment, participant):
        is_creator = super().is_create_trial()
        if is_creator:
            return self.show_create_trial(experiment, participant)
        else:
            return self.show_rate_trial(experiment, participant)


def get_non_failed_creations(node):
    return [
        t
        for t in node.all_trials
        if t.var.has(ROLE_KEY)
        and t.var.get(ROLE_KEY) == CREATOR_KEY
        and t.answer is not None
        and t.failed is False
    ]


class CustomNode(ChainNode, CreateAndRateNode):
    def create_initial_seed(self, experiment, participant):
        pass

    def create_definition_from_seed(self, seed, experiment, participant):
        pass

    def summarize_trials(self, trials: list, experiment, participant):
        pass


start_nodes = [CustomNode(context=d) for d in dummy_data]


class CustomTrialMaker(ImitationChainTrialMaker, CreateAndRateTrialMaker):
    response_timeout_sec = MAX_TIME
    num_creators = CREATE_TRIALS
    num_raters = RATE_TRIALS

    def find_networks(self, participant, experiment):
        # Obtain available networks
        networks = super().find_networks(
            participant, experiment, return_one_network=False
        )
        if type(networks) is str:
            # return "exit", "wait"
            return networks
        return super().filter_networks(networks, participant)

    def finalize_trial(self, answer, trial, experiment, participant):
        super().finalize_trial(answer, trial, experiment, participant)
        visited_rule_ids = participant.var.get(VISITED_RULE_IDS_KEY, [])
        visited_rule_ids.append(trial.node.context["rule_id"])
        participant.var.set(VISITED_RULE_IDS_KEY, visited_rule_ids)


##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "Picnic"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        instructions,
        CustomTrialMaker(
            id_="picnic",
            trial_class=CustomTrial,
            node_class=CustomNode,
            chain_type="across",
            expected_trials_per_participant=len(start_nodes),
            max_trials_per_participant=len(start_nodes),
            start_nodes=start_nodes,
            chains_per_experiment=len(start_nodes),
            balance_across_chains=False,
            check_performance_at_end=True,
            check_performance_every_trial=False,
            propagate_failure=False,
            recruit_mode="n_trials",
            target_n_participants=None,
            wait_for_networks=True,
            max_nodes_per_chain=NUM_ITERATIONS,
            trials_per_node=CREATE_TRIALS + RATE_TRIALS,
        ),
        final_questionnaire,
        SuccessfulEndPage(),
    )
