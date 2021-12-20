# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import Prompt, ColorPrompt, PushButtonControl, NullControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.timeline import Event, MediaSpec
from typing import Dict, List, Optional, Union

from psynet.trial.dense import (
    Condition,
    ConditionList,
    DenseTrialMaker,
    Dimension,
    SingleStimulusTrial,
    SameDifferentTrial

)
from psynet.utils import get_logger
from flask import Markup, escape
import json

logger = get_logger()

PARAMS = {
    "dimensions": [
        Dimension("Hue", min_value=0, max_value=360),
        Dimension("Saturation", min_value=0, max_value=100),
        Dimension("Lightness", min_value=0, max_value=100),
    ]
}

CONDITIONS_PREFERENE = ConditionList(
    "color",
    conditions=[
        Condition(
            {
                **PARAMS,
                "adjective": "angry",
            }
        ),
        Condition(
            {
                **PARAMS,
                "adjective": "happy",
            }
        ),
    ],
)

CONDITIONS_DISCRIMINATION = ConditionList(
    "color",
    conditions=[
        Condition(
            {
                **PARAMS,
                "delta": 30,
                "bonus_per_correct_response":0.01
            }
        ),
    ],
)

class ColorSameDiff(SameDifferentTrial):
    __mapper_args__ = {"polymorphic_identity": "same_diff_trial"}

    time_estimate = 5
    num_pages = 3
    accumulate_answers = False

    def show_trial(self, experiment, participant):
        order = self.definition["order"]
        color1 = self.definition["locations"][order[0]]
        color2 = self.definition["locations"][order[1]]
        correct_answer= self.definition["correct_answer"]

        page1 = ModularPage(
            prompt=ColorPrompt(color=color1, text="First color"),
            label="color_page_1",
            time_estimate=2
        )
        page2 = ModularPage(
            prompt=ColorPrompt(color=color2, text="Second color"),
            label="color_page_2",
            time_estimate=2
        )
        page3 = ModularPage(
            "color1",
            prompt = Prompt(text="Was the first color same or different than the second color?"),
            control = PushButtonControl(choices=["same", "different"], arrange_vertically=False),
            time_estimate=self.time_estimate,
        )

        return [page1,page2,page3]

    def compute_bonus(self, score):
        return score * self.definition["bonus_per_correct_response"]

    def show_feedback(self, experiment, participant):
        assert self.score in [0, 1]
        if self.score:
            feedback = f"Correct - you win ${self.bonus:.2f}!"
        else:
            correct_answer = self.definition['correct_answer']
            feedback = f"Incorrect - you should have answered '{correct_answer}'."

        return InfoPage(feedback, time_estimate=3)

class CustomTrial(SingleStimulusTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    time_estimate = 5

    def show_trial(self, experiment, participant):
        adjective = self.definition["adjective"]
        color = self.definition["location"]
        caption = f"Please rate how well the color matches the following adjective: {adjective}"

        return ModularPage(
            "color",
            ColorPrompt(color=color, text=caption),
            PushButtonControl(choices=[1, 2, 3, 4], arrange_vertically=False),
            time_estimate=self.time_estimate,
        )


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "In the part of the experiment, you will see briefly two colors, memorize the colors and respond if they are the same or different.",
            time_estimate=0),
        DenseTrialMaker(
            id_="color_discrimination",
            trial_class=ColorSameDiff,
            conditions=CONDITIONS_DISCRIMINATION,
            recruit_mode="num_participants",
            target_num_participants=1,
            target_num_trials_per_condition=None,
            max_trials_per_block=6,
        ),
        InfoPage("In this part of the experiment you will be rating colors", time_estimate=0),
        DenseTrialMaker(
            id_="color_preferences",
            trial_class=ColorSameDiff,
            conditions=CONDITIONS_PREFERENE,
            recruit_mode="num_participants",
            target_num_participants=1,
            target_num_trials_per_condition=None,
            max_trials_per_block=6,
        ),
        SuccessfulEndPage(),
    )
