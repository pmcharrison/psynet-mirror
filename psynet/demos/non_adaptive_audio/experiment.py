import psynet.experiment
from psynet.timeline import (
    Timeline,
)
from psynet.page import (
    SuccessfulEndPage,
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

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

##########################################################################################
#### Stimuli
##########################################################################################

# Prepare the audio stimuli by running the following command:
# python3 experiment.py

class CustomStimulusVersionSpec(StimulusVersionSpec):
    has_media = True
    media_ext = ".wav"

    @classmethod
    def generate_media(cls, definition, output_path):
        from custom_synth import synth_stimulus
        synth_stimulus(definition["frequencies"], output_path)

stimuli = [
    StimulusSpec(
        definition={
            "frequency_gradient": frequency_gradient,
        },
        version_specs=[
            CustomStimulusVersionSpec(
                definition={
                    "start_frequency": start_frequency,
                    "frequencies": [start_frequency + i * frequency_gradient for i in range(5)]
                }
            )
            for start_frequency in [-100, 0, 100]
        ],
        phase="experiment"
    )
    for frequency_gradient in [-100, -50, 0, 50, 100]
]

stimulus_set = StimulusSet(stimuli, version="v2", s3_bucket="non-adaptive-audio-demo")

if __name__ == "__main__":
    stimulus_set.prepare_media()

class CustomTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        return ModularPage(
            "question_page",
            AudioPrompt(self.media_url, "Is the speaker asking a question?"),
            NAFCControl(["Yes", "No"]),
            time_estimate=5
        )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NonAdaptiveTrialMaker(
            trial_class=CustomTrial,
            phase="experiment",
            stimulus_set=stimulus_set,
            time_estimate_per_trial=5,
            new_participant_group=True,
            target_num_participants=3,
            recruit_mode="num_participants"
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
