# pylint: disable=unused-import,abstract-method,unused-argument

import random
from statistics import mean

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.graphics import GraphicPrompt
from psynet.modular_page import ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.imitation_chain import (
    ImitationChainNetwork,
    ImitationChainNode,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


class CustomTrial(ImitationChainTrial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage("dot_trial", prompt=GraphicPrompt())


class CustomNetwork(ImitationChainNetwork):
    pass


class CustomNode(ImitationChainNode):
    def create_initial_seed(self, experiment, participant):
        return {"number": random.randint(0, 9999999)}

    def summarize_trials(self, trials: list, experiment, participant):
        return {"number": round(mean([trial.answer for trial in trials]))}


class CustomTrialMaker(ImitationChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval_sec = 30


class Exp(psynet.experiment.Experiment):
    label = "Imitation chain demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        CustomTrialMaker(
            id_="imitation_chain",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            chain_type="within",
            max_nodes_per_chain=5,
            max_trials_per_participant=5,
            expected_trials_per_participant=5,
            chains_per_participant=1,
            chains_per_experiment=None,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="n_participants",
            target_n_participants=10,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.alive_trials) == 5
