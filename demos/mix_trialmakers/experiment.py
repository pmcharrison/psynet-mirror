# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline, for_loop, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


nodes_1 = [
    StaticNode(
        definition={"animal": animal},
        block=block,
    )
    for animal in ["cats", "dogs", "fish", "ponies"]
    for block in ["A", "B", "C"]
]


class AnimalTrial(StaticTrial):
    time_estimate = 3

    def show_trial(self, experiment, participant):
        animal = self.definition["animal"]
        return ModularPage(
            "animal_trial",
            f"How much do you like {animal}?",
            PushButtonControl(
                ["Not at all", "A little", "Very much"],
            ),
            time_estimate=self.time_estimate,
        )


nodes_2 = [
    StaticNode(
        definition={"color": color},
        block=block,
    )
    for color in ["red", "green", "blue", "orange"]
    for block in ["A", "B", "C"]
]


class ColorTrial(StaticTrial):
    time_estimate = 3

    def show_trial(self, experiment, participant):
        color = self.definition["color"]
        return ModularPage(
            "color_trial",
            f"How much do you like {color}?",
            PushButtonControl(
                ["Not at all", "A little", "Very much"],
            ),
            time_estimate=self.time_estimate,
        )


trial_maker_1 = StaticTrialMaker(
    id_="animals",
    trial_class=AnimalTrial,
    nodes=nodes_1,
    num_trials_per_participant=6,
    max_trials_per_block=2,
    allow_repeated_nodes=True,
    active_balancing_within_participants=True,
    active_balancing_across_participants=True,
    check_performance_at_end=True,
    check_performance_every_trial=True,
    target_num_participants=1,
    target_num_trials_per_node=None,
    recruit_mode="num_participants",
    num_repeat_trials=3,
)

trial_maker_2 = StaticTrialMaker(
    id_="colors",
    trial_class=ColorTrial,
    nodes=nodes_2,
    num_trials_per_participant=6,
    max_trials_per_block=2,
    allow_repeated_nodes=True,
    active_balancing_within_participants=True,
    active_balancing_across_participants=True,
    check_performance_at_end=True,
    check_performance_every_trial=True,
    target_num_participants=1,
    target_num_trials_per_node=None,
    recruit_mode="num_participants",
    num_repeat_trials=3,
)


##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "Static experiment demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        trial_maker_1.custom(
            trial_maker_2.custom(
                for_loop(
                    label="loop over pairs of trials",
                    iterate_over=lambda: range(3),
                    logic=lambda _: join(
                        trial_maker_1.cue_trial(),
                        trial_maker_2.cue_trial(),
                    ),
                    time_estimate_per_iteration=6,
                )
            )
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.trials) == 6
        trials = sorted(bot.trials, key=lambda t: t.id)
        for i in [0, 2, 4]:
            assert isinstance(trials[i], AnimalTrial)
        for i in [1, 3, 5]:
            assert isinstance(trials[i], ColorTrial)
