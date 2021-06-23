"""
Video Imitation Chain Demo
"""
import random
import shutil
import tempfile

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import download_from_s3, prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import (
    AudioMeterControl,
    ModularPage,
    Prompt,
    VideoPrompt,
    VideoRecordControl,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import (
    Event,
    PreDeployRoutine,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    join,
)
from psynet.trial.video import (
    CameraImitationChainNetwork,
    CameraImitationChainNode,
    CameraImitationChainSource,
    CameraImitationChainTrial,
    CameraImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()

SILENT_RECORDING = "./static/5s_silence.wav"


class CustomNetwork(CameraImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}
    s3_bucket = "video-screen-recording-dev"


class CustomSource(CameraImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        possibilities = ["Figure 8", "Circle", "Triangle", "Square"]
        return random.choice(possibilities)


class CustomVideoRecordControl(VideoRecordControl):
    def __init__(self):
        super().__init__(
            duration=5.0,
            s3_bucket="video-screen-recording-dev",
            recording_source="camera",
            audio_num_channels=2,
            controls=True,
            public_read=True,
            show_preview=True,
        )


class CustomProgressDisplay(ProgressDisplay):
    def __init__(self):
        super().__init__(
            duration=1.5 + 5.0,
            stages=[
                ProgressStage([0.0, 1.5], "Get ready...", color="grey"),
                ProgressStage([1.5, 1.5 + 5.0], "Make your gesture!", color="red"),
                ProgressStage(
                    [1.5 + 5.0, 1.5 + 5.0],
                    "Click 'upload' if you're happy with your recording.",
                    color="green",
                    persistent=True,
                ),
            ],
        )


class CustomTrial(CameraImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        if self.origin.degree == 1:
            instruction = f"Please trace out a {self.origin.seed} in the air \
                            for the camera using you hands or fingers."
            return ModularPage(
                "first-iteration-record",
                Prompt(text=instruction, text_align="center"),
                CustomVideoRecordControl(),
                time_estimate=5,
                progress_display=CustomProgressDisplay(),
                events={"recordStart": Event(is_triggered_by="trialStart", delay=1.5)},
            )
        else:
            return join(
                [
                    ModularPage(
                        "subsequent-iteration-prompt",
                        VideoPrompt(
                            self.origin.target_url,
                            "When you are ready, press next to imitate the figure that you see.",
                            text_align="center",
                            width="360px",
                        ),
                        time_estimate=5,
                    ),
                    ModularPage(
                        "subsequent-iteration-record",
                        prompt="",
                        control=CustomVideoRecordControl(),
                        time_estimate=5,
                        progress_display=CustomProgressDisplay(),
                    ),
                ]
            )

    def analyze_recording(self, experiment, participant):
        return {"failed": False}


class CustomCameraImitationTrialMaker(CameraImitationChainTrialMaker):
    pass


class CustomNode(CameraImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarize_trials(self, trials, experiment, participant):
        recording_info = trials[0].recording_info
        logger.info("RECORDING INFO: {}".format(recording_info))
        analysis = trials[0].analysis
        return dict(recording_info=recording_info, analysis=analysis)

    def synthesize_target(self, output_file):
        """
        This code can be modified to introduce custom video editing before reuploading the video.
        """
        if self.degree == 1:
            shutil.copyfile(SILENT_RECORDING, output_file)
            return output_file
        else:
            prev_trial = self.definition
            with tempfile.NamedTemporaryFile() as temp_file:
                recording = prev_trial["recording_info"]
                download_from_s3(
                    temp_file.name, recording["s3_bucket"], recording["key"]
                )
                # Processing of temp_file.name file.
                shutil.copyfile(temp_file.name, output_file)
                return output_file


####################################################################################################
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": "video-screen-recording-dev",
                "public_read": True,
                "create_new_bucket": True,
            },
        ),
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
        CustomCameraImitationTrialMaker(
            id_="video-chain",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_estimate_per_trial=15,
            chain_type="within",
            num_trials_per_participant=4,
            num_iterations_per_chain=4,
            num_chains_per_experiment=None,
            num_chains_per_participant=2,
            trials_per_node=1,
            balance_across_chains=False,
            recruit_mode="num_participants",
            check_performance_at_end=True,
            check_performance_every_trial=False,
            target_num_participants=25,
            wait_for_networks=True,
        ),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
