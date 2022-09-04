"""
Video Imitation Chain Demo
"""
import random

import psynet.experiment
from psynet.asset import Asset, CachedAsset, DebugStorage, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioMeterControl,
    ModularPage,
    Prompt,
    VideoPrompt,
    VideoRecordControl,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline, join
from psynet.trial.video import (
    CameraImitationChainNode,
    CameraImitationChainTrial,
    CameraImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


class CustomVideoRecordControl(VideoRecordControl):
    def __init__(self, **kwargs):
        super().__init__(
            duration=5.0,
            recording_source="camera",
            audio_n_channels=2,
            controls=True,
            show_preview=True,
            **kwargs,
        )


def custom_progress_display():
    return ProgressDisplay(
        [
            ProgressStage([0.0, 1.5], "Get ready...", color="grey"),
            ProgressStage([1.5, 1.5 + 5.0], "Make your gesture!", color="red"),
            ProgressStage(
                [1.5 + 5.0, 1.5 + 5.0],
                "Click 'Next' if you're happy with your recording.",
                color="green",
                persistent=True,
            ),
        ]
    )


class CustomTrial(CameraImitationChainTrial):
    time_estimate = 15

    def show_trial(self, experiment, participant):
        if self.degree == 0:
            instruction = f"Please trace out a {self.origin.seed} in the air \
                            for the camera using your hands or fingers."
            return ModularPage(
                "webcam_recording",
                Prompt(text=instruction, text_align="center"),
                CustomVideoRecordControl(
                    bot_response_media="assets/example_recording.webm",
                ),
                time_estimate=5,
                progress_display=custom_progress_display(),
                events={"recordStart": Event(is_triggered_by="trialStart", delay=1.5)},
            )
        else:
            return join(
                [
                    ModularPage(
                        "webcam_prompt",
                        VideoPrompt(
                            self.assets["stimulus"],
                            "When you are ready, press next to imitate the figure that you see.",
                            text_align="center",
                            width="360px",
                        ),
                        time_estimate=5,
                    ),
                    ModularPage(
                        "webcam_recording",
                        prompt="",
                        control=CustomVideoRecordControl(
                            bot_response_media="assets/example_recording.webm",
                        ),
                        time_estimate=5,
                        progress_display=custom_progress_display(),
                    ),
                ]
            )

    def analyze_recording(self, experiment, participant):
        return {"failed": False}


class CustomNode(CameraImitationChainNode):
    def create_initial_seed(self, experiment, participant):
        possibilities = ["Figure 8", "Circle", "Triangle", "Square"]
        return random.choice(possibilities)

    def summarize_trials(self, trials, experiment, participant):
        assert len(trials) == 1
        trial = trials[0]
        return dict(recording_info=trial.recording_info, analysis=trial.analysis)

    def synthesize_target(self, output_file):
        """
        This code can be modified to introduce custom video editing before reuploading the video.
        """
        if self.degree == 0:
            self.trial_maker.assets["5s_silence"].export(output_file)
        else:
            self.parent.alive_trials[0].assets["webcam_recording"].export(output_file)


####################################################################################################
class Exp(psynet.experiment.Experiment):
    label = "Video imitation chain demo"

    # asset_storage = S3Storage("psynet-demos", "video-imitation-chain")
    asset_storage = DebugStorage()

    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
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
        CameraImitationChainTrialMaker(
            id_="video-chain",
            trial_class=CustomTrial,
            node_class=CustomNode,
            chain_type="within",
            expected_trials_per_participant=8,
            max_nodes_per_chain=4,
            chains_per_experiment=None,
            chains_per_participant=2,
            trials_per_node=1,
            balance_across_chains=False,
            recruit_mode="n_participants",
            check_performance_at_end=True,
            check_performance_every_trial=False,
            target_n_participants=25,
            wait_for_networks=True,
            assets=[
                CachedAsset(local_key="5s_silence", input_path="assets/5s_silence.wav"),
            ],
        ),
        SuccessfulEndPage(),
    )
