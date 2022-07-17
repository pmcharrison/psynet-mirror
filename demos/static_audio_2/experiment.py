import random

import psynet.experiment
from psynet.asset import FastFunctionAsset, LocalStorage, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
)
from psynet.page import InfoPage, SuccessfulEndPage, VolumeCalibration
from psynet.timeline import Timeline
from psynet.trial.static import StaticTrial, StaticTrialMaker, Stimulus

from .custom_synth import synth_prosody

##########################################################################################
# Stimuli
##########################################################################################


def synth_stimulus(path, frequencies):
    synth_prosody(vector=frequencies, output_path=path)


# Here we define the stimulus set in an analogous way to the static_audio demo,
# except we randomise the start_frequency from a continuous range.
stimuli = [
    Stimulus(
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
                "audio": FastFunctionAsset(
                    function=synth_stimulus,
                    extension=".wav",
                )
            }
        )
        return definition

    def show_trial(self, experiment, participant):
        return ModularPage(
            "imitation_page",
            AudioPrompt(
                self.stimulus.assets["audio"].url,
                "Please imitate the spoken word as closely as possible.",
            ),
            AudioRecordControl("imitation", duration=3.0),
            time_estimate=self._time_trial,
        )

    def show_feedback(self, experiment, participant):
        return ModularPage(
            "feedback_page",
            AudioPrompt(
                self.assets["imitation"].url,
                "Listen back to your recording. Did you do a good job?",
            ),
            time_estimate=self._time_feedback,
        )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Static audio demo"
    asset_storage = LocalStorage("~/Downloads/psynet_local_storage")
    # asset_storage = S3Storage("psynet-demos", "static-audio")

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
            id_="static_audio",
            trial_class=CustomTrial,
            phase="experiment",
            stimuli=stimuli,
            target_num_participants=3,
            recruit_mode="num_participants",
        ),
        SuccessfulEndPage(),
    )
