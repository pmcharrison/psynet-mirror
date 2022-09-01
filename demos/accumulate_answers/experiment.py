# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import CodeBlock, PageMaker, Timeline, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def animal_page(animal, time_estimate, bot_response):
    return ModularPage(
        "animal",
        f"How much do you like {animal}?",
        PushButtonControl(
            ["Not at all", "A little", "Very much"],
        ),
        time_estimate=time_estimate,
        bot_response=bot_response,
    )


def color_page(color, time_estimate, bot_response):
    return ModularPage(
        "color",
        f"How much do you like {color}?",
        PushButtonControl(
            ["Not at all", "A little", "Very much"],
        ),
        time_estimate=time_estimate,
        bot_response=bot_response,
    )


nodes_1 = [
    StaticNode(
        definition={"animal": animal},
        block=block,
    )
    for animal in ["cats", "dogs", "fish", "ponies"]
    for block in ["A", "B", "C"]
]


class AnimalTrial(StaticTrial):
    time_estimate = 10
    accumulate_answers = True

    def show_trial(self, experiment, participant):
        animal = self.definition["animal"]
        return join(
            ModularPage(
                "kindness",
                f"How kind is the following animal: {animal}",
                PushButtonControl(["Not at all", "A little", "Very much"]),
                time_estimate=5,
                bot_response="Very much",
            ),
            ModularPage(
                "bravery",
                f"How brave is the following animal: {animal}",
                PushButtonControl(["Not at all", "A little", "Very much"]),
                time_estimate=5,
                bot_response="A little",
            ),
        )


trial_maker_1 = StaticTrialMaker(
    id_="animals",
    trial_class=AnimalTrial,
    nodes=nodes_1,
    num_trials_per_participant=3,
    max_trials_per_block=1,
    target_num_participants=1,
    target_num_trials_per_node=None,
    recruit_mode="num_participants",
)

part_1_logic = PageMaker(
    lambda: join(
        animal_page("dog", time_estimate=5, bot_response="Very much"),
        color_page("red", time_estimate=5, bot_response="A little"),
    ),
    time_estimate=10,
    accumulate_answers=True,
)


def part_1_check(participant):
    assert participant.answer == {"dog": "Very much", "color": "A little"}


part_1 = join(
    part_1_logic,
    CodeBlock(part_1_check),
)


def part_2_check(participant):
    assert len(participant.trials) == 3
    trial = participant.trials[0]
    assert trial.answer == {"kindness": "Very much", "bravery": "A little"}


part_2 = join(
    trial_maker_1,
    CodeBlock(part_2_check),
)


##########################################################################################
# Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    label = "Static experiment demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        part_1,
        part_2,
        SuccessfulEndPage(),
    )
