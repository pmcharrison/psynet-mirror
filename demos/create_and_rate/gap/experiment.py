# pylint: disable=unused-import,abstract-method,unused-argument
##########################################################################################
# Imports
##########################################################################################
from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ImagePrompt, ModularPage, PushButtonControl, TextControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.create_and_rate import (
    CreateAndRateNode,
    CreateAndRateTrialMakerMixin,
    CreateTrialMixin,
    SelectTrialMixin,
)
from psynet.trial.imitation_chain import ImitationChainTrial, ImitationChainTrialMaker
from psynet.utils import get_logger

logger = get_logger()


def animal_prompt(text, img_url):
    return ImagePrompt(
        url=img_url,
        text=Markup(text),
        width="300px",
        height="300px",
    )


class CreateTrial(CreateTrialMixin, ImitationChainTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "create_trial",
            animal_prompt(text="Describe the animal", img_url=self.context["img_url"]),
            TextControl(),
            time_estimate=self.time_estimate,
        )


class SelectTrial(SelectTrialMixin, ImitationChainTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        target_strs = [f"{target}" for target in self.targets]
        answers = [self.get_target_answer(target) for target in self.targets]
        return ModularPage(
            "select_trial",
            animal_prompt(
                text="Which of these descriptions is the best?",
                img_url=self.context["img_url"],
            ),
            PushButtonControl(
                choices=target_strs,
                labels=answers,
            ),
        )


class CreateAndRateTrialMaker(CreateAndRateTrialMakerMixin, ImitationChainTrialMaker):
    pass


##########################################################################################
# Experiment
##########################################################################################


n_creators = 2
n_raters = 2
rate_mode = "rate"
include_previous_iteration = True
target_selection_method = "one"


rater_class = SelectTrial
n_raters = 3
target_selection_method = "all"
rate_mode = "select"

seed_definition = "initial creation" if include_previous_iteration else {}
start_nodes = [
    CreateAndRateNode(context={"img_url": "static/dog.jpg"}, seed=seed_definition)
]

trial_maker = CreateAndRateTrialMaker(
    n_creators=n_creators,
    n_raters=n_raters,
    node_class=CreateAndRateNode,
    creator_class=CreateTrial,
    rater_class=SelectTrial,
    # mixin params
    include_previous_iteration=include_previous_iteration,
    rate_mode=rate_mode,
    target_selection_method=target_selection_method,
    verbose=True,  # for the demo
    # trial_maker params
    id_="trial_maker",
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
    wait_for_networks=False,
    max_nodes_per_chain=10,
)


available_demos = ["include_previous_iteration", "rate", "select"]


class Exp(psynet.experiment.Experiment):
    label = "Basic Create and Rate Experiment"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "pick_demo_page",
            "Pick a demo you are interested in.",
            PushButtonControl(
                choices=available_demos,
                labels=[
                    "Rate creation + previous iteration",
                    "Rate two creations",
                    "Select from two creations + previous iteration",
                ],
            ),
            time_estimate=1,
        ),
        trial_maker,
        SuccessfulEndPage(),
    )
