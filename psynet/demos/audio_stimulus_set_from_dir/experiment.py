from flask import Markup, escape
import json

import psynet.experiment
from psynet.timeline import (
    Timeline,
)
from psynet.page import (
    SuccessfulEndPage,
    InfoPage
)
from psynet.modular_page import(
    ModularPage,
    AudioPrompt,
    NAFCControl
)
from psynet.trial.non_adaptive import (
    NonAdaptiveTrialMaker,
    NonAdaptiveTrial,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec
)
from psynet.helpers import audio_stimulus_set_from_dir

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

##########################################################################################
#### Stimuli
##########################################################################################

stimulus_set = audio_stimulus_set_from_dir("input", version="v1", s3_bucket="audio-stimulus-set-from-dir-demo")

# Run ``python3 experiment.py`` to prepare the stimulus set.
if __name__ == "__main__":
    stimulus_set.prepare_media()


class CustomTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        text = Markup(f"<pre>{escape(json.dumps(self.summarise(), indent=4))}</pre>")

        return ModularPage(
            "question_page",
            AudioPrompt(self.media_url, text),
            NAFCControl(["Yes", "No"]),
            time_estimate=5
        )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage("We begin with the practice trials.", time_estimate=5),
        NonAdaptiveTrialMaker(
            trial_class=CustomTrial,
            phase="practice",
            stimulus_set=stimulus_set,
            time_estimate_per_trial=5,
            new_participant_group=True,
            target_num_participants=3,
            recruit_mode="num_participants"
        ),
        InfoPage("We continue with the experiment trials.", time_estimate=5),
        NonAdaptiveTrialMaker(
            trial_class=CustomTrial,
            phase="experiment",
            stimulus_set=stimulus_set,
            time_estimate_per_trial=5,
            new_participant_group=False,
            target_num_participants=3,
            recruit_mode="num_participants"
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
