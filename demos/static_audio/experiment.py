import psynet.experiment
from psynet.asset import CachedFunctionAsset, DebugStorage, S3Storage  # noqa
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


stimuli = [
    Stimulus(
        definition={
            "frequency_gradient": frequency_gradient,
            "start_frequency": start_frequency,
            "frequencies": [start_frequency + i * frequency_gradient for i in range(5)],
        },
        assets={
            "audio": CachedFunctionAsset(
                function=synth_stimulus,
                extension=".wav",
            )
        },
    )
    for frequency_gradient in [-100, -50, 0, 50, 100]
    for start_frequency in [-100, 0, 100]
]


class CustomTrial(StaticTrial):
    _time_trial = 3
    _time_feedback = 2

    time_estimate = _time_trial + _time_feedback
    wait_for_feedback = True

    def show_trial(self, experiment, participant):
        return ModularPage(
            "imitation",
            AudioPrompt(
                self.stimulus.assets["audio"],
                "Please imitate the spoken word as closely as possible.",
            ),
            AudioRecordControl(duration=3.0, bot_response_media="example-bier.wav"),
            time_estimate=self._time_trial,
        )

    def show_feedback(self, experiment, participant):
        return ModularPage(
            "feedback",
            AudioPrompt(
                self.assets["imitation"],
                "Listen back to your recording. Did you do a good job?",
            ),
            time_estimate=self._time_feedback,
        )


class Exp(psynet.experiment.Experiment):
    label = "Static audio demo"
    # asset_storage = DebugStorage()
    asset_storage = S3Storage(
        "psynet-demos", "static-audio"
    )  # We use this S3Storage for the CI tests

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
