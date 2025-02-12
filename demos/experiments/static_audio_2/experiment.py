import random

import psynet.experiment
from psynet.asset import LocalStorage, OnDemandAsset, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
)
from psynet.page import InfoPage, SuccessfulEndPage, VolumeCalibration
from psynet.timeline import Timeline
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

from .custom_synth import synth_prosody

##########################################################################################
# Stimuli
##########################################################################################


def synth_stimulus(path, frequencies):
    synth_prosody(vector=frequencies, output_path=path)


# Here we define the stimulus set in an analogous way to the static_audio demo,
# except we randomise the start_frequency from a continuous range.
nodes = [
    StaticNode(
        definition={
            "frequency_gradient": frequency_gradient,
        },
    )
    for frequency_gradient in [-100, -50, 0, 50, 100]
]


class CustomTrial(StaticTrial):
    _time_trial = 3
    _time_feedback = 2

    time_estimate = _time_trial + _time_feedback
    wait_for_feedback = True

    def finalize_definition(self, definition, experiment, participant):
        definition["start_frequency"] = random.uniform(-100, 100)
        definition["frequencies"] = [
            definition["start_frequency"] + i * definition["frequency_gradient"]
            for i in range(5)
        ]
        self.add_assets(
            {
                "stimulus": OnDemandAsset(
                    function=synth_stimulus,
                    extension=".wav",
                )
            }
        )
        return definition

    def show_trial(self, experiment, participant):
        return ModularPage(
            "imitation",
            AudioPrompt(
                self.assets["stimulus"],
                "Please imitate the spoken word as closely as possible.",
            ),
            AudioRecordControl(duration=3.0, bot_response_media="example-bier.wav"),
            time_estimate=self._time_trial,
        )

    def show_feedback(self, experiment, participant):
        return ModularPage(
            "feedback_page",
            AudioPrompt(
                self.assets["imitation"],
                "Listen back to your recording. Did you do a good job?",
            ),
            time_estimate=self._time_feedback,
        )


class Exp(psynet.experiment.Experiment):
    label = "Static audio demo (2)"

    # asset_storage = S3Storage("psynet-tests", "static-audio")

    timeline = Timeline(
        NoConsent(),
        VolumeCalibration(),
        ModularPage(
            "record_calibrate",
            """
            Please speak into your microphone and check that the sound is registered
            properly. If the sound is too quiet, try moving your microphone
            closer or increasing the input volume on your computer.
            """,
            AudioMeterControl(),
            time_estimate=5,
        ),
        InfoPage(
            """
            In this experiment you will hear some words. Your task will be to repeat
            them back as accurately as possible.
            """,
            time_estimate=5,
        ),
        StaticTrialMaker(
            id_="static_audio_2",
            trial_class=CustomTrial,
            nodes=nodes,
            expected_trials_per_participant=len(nodes),
            target_n_participants=3,
            recruit_mode="n_participants",
        ),
        SuccessfulEndPage(),
    )
