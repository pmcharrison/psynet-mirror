import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
)
from psynet.page import InfoPage, SuccessfulEndPage, VolumeCalibration
from psynet.timeline import PreDeployRoutine, Timeline
from psynet.trial.static import (
    StaticTrial,
    StaticTrialMaker,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec,
)

from .custom_synth import synth_stimulus

##########################################################################################
# Stimuli
##########################################################################################

# Prepare the audio stimuli by running the following command:
# python3 experiment.py


class CustomStimulusVersionSpec(StimulusVersionSpec):
    has_media = True
    media_ext = ".wav"

    @classmethod
    def generate_media(cls, definition, output_path):
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
                    "frequencies": [
                        start_frequency + i * frequency_gradient for i in range(5)
                    ],
                }
            )
            for start_frequency in [-100, 0, 100]
        ],
        phase="experiment",
    )
    for frequency_gradient in [-100, -50, 0, 50, 100]
]

stimulus_set = StimulusSet(
    "static_audio",
    stimuli,
    version="v3",
    s3_bucket="static-audio-demo-stimuli",
)
recordings_s3_bucket = "static-audio-demo-stimuli-recordings"


class CustomTrial(StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        return ModularPage(
            "question_page",
            AudioPrompt(
                self.media_url, "Please imitate the spoken word as closely as possible."
            ),
            AudioRecordControl(
                duration=3.0, s3_bucket=recordings_s3_bucket, public_read=True
            ),
            time_estimate=5,
        )

    def show_feedback(self, experiment, participant):
        return ModularPage(
            "feedback_page",
            AudioPrompt(
                participant.answer["url"],
                "Listen back to your recording. Did you do a good job?",
            ),
            time_estimate=2,
        )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": recordings_s3_bucket,
                "public_read": True,
                "create_new_bucket": True,
            },
        ),
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
            stimulus_set=stimulus_set,
            time_estimate_per_trial=5,
            target_num_participants=3,
            recruit_mode="num_participants",
        ),
        SuccessfulEndPage(),
    )
