# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ColorPrompt, PushButtonControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.dense import (
    Condition,
    ConditionList,
    DenseTrialMaker,
    Dimension,
    SingleStimulusTrial,
)
from psynet.utils import get_logger

logger = get_logger()

PARAMS = {
    "dimensions": [
        Dimension("Hue", min_value=0, max_value=360),
        Dimension("Saturation", min_value=0, max_value=100),
        Dimension("Lightness", min_value=0, max_value=100),
    ]
}

CONDITIONS = ConditionList(
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


class CustomTrial(SingleStimulusTrial):
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
    label = "Dense color demo"

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        DenseTrialMaker(
            id_="color",
            trial_class=CustomTrial,
            conditions=CONDITIONS,
            recruit_mode="num_participants",
            target_num_participants=1,
            target_num_trials_per_condition=None,
            max_trials_per_block=6,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )
