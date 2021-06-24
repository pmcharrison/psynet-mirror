# Iterated tapping from memory, adapted from Jacoby & McDermott (2017)
import json
from statistics import mean

import numpy as np
from flask import Markup
from repp.config import ConfigUpdater, sms_tapping

# repp imports
from reppextension.iterated_tapping import (
    REPPAnalysisItapMemory,
    REPPStimulusItapMemory,
)
from scipy.io import wavfile

import psynet.experiment
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import JSONSerializer, REPPTappingCalibration
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline
from psynet.trial.audio import (
    AudioImitationChainNetwork,
    AudioImitationChainNode,
    AudioImitationChainSource,
    AudioImitationChainTrial,
    AudioImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


# Global parameters
BUCKET_NAME = "iterated-tapping-demo"
config = ConfigUpdater.create_config(
    sms_tapping,
    {
        "LABEL": "iterated tapping from memory (2-interval)",
        "USE_CLICK_FILENAME": True,
        "ONSET_MATCHING_WINDOW": 200.0,
        "CLEAN_NORMALIZE_FACTOR": 0.1,
        "PLOTS_TO_DISPLAY": [2, 2],
        "STIM_RANGE": [30, 800],
        "STIM_AMPLITUDE": 0.15,
        "INTERVAL_RHYTHM": 2,
        "REPEATS": 3,
        "MIN_RATIO": 1.0 / 10.0,
        "SLACK_RATIO": 0.95,
        "DURATION_RANGE": [250, 2000],
        "TOTAL_DURATION": 1000,
        "PROB_NO_CHANGE": 1 / 3,
        "MAX_DIFF_RATIO": 0.25,
        "MAX_DIF_IOI": 500,
        "IS_FIXED_DURATION": False,
        "MIN_TAPS_PLAYED": 5,
        "EXTRACT_SECOND_WINDOW": [26, 60],
        "SAMPLE_LOG_SCALE": True,
    },
)

stimulus = REPPStimulusItapMemory("itap_memory", config=config)
analysis_itap = REPPAnalysisItapMemory(config=config)

TIME_ESTIMATE_PER_TRIAL = config.REPEATS * 3

# failing criteria
MIN_RESPONSES_PLAYED = config.MIN_TAPS_PLAYED
# within chains
NUM_CHAINS_PER_PARTICIPANT = 2  # set to 4 for a real experiment
NUM_ITERATION_CHAIN = 2  # set to 5 for a real experiment
NUM_TRIALS_PARTICIPANT = 4  # set to 20 for a real experiment
TOTAL_NUM_PARTICIPANTS = 50


# Experiment parts
def save_samples_to_file(samples, filename, fs):
    wavfile.write(filename, rate=fs, data=samples.astype(np.float32))


def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x


class CustomTrialAnalysis(AudioImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial_analysis"}

    def analyze_recording(self, audio_file: str, output_plot: str):
        info_stimulus = self.origin.var.info_stimulus
        title_in_graph = "Participant {}".format(self.participant_id)
        _, output_iteration = analysis_itap.do_analysis(
            info_stimulus["random_seed"], audio_file, title_in_graph, output_plot
        )
        new_seed = output_iteration["new_ioi_seed"]
        old_seed = output_iteration["old_ioi_seed"]
        failed = output_iteration["seed_needs_change"]
        reason = output_iteration["seed_needs_change_reason"]
        ratios_reps = output_iteration["resp_onsets_complete"]
        ratios_reps = json.dumps(ratios_reps, cls=JSONSerializer)
        output_iteration = json.dumps(output_iteration, cls=JSONSerializer)
        ioi_new_seed = [as_native_type(value) for value in new_seed]
        ioi_old_seed = [as_native_type(value) for value in old_seed]
        return {
            "failed": failed,
            "reason": reason,
            "ioi_new_seed": ioi_new_seed,
            "ioi_old_seed": ioi_old_seed,
            "ratios_reps": ratios_reps,
            "output_iteration": output_iteration,
        }


class CustomTrial(CustomTrialAnalysis):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        info_stimulus = self.origin.var.info_stimulus
        duration_rec_sec = info_stimulus["duration_rec_sec"]
        trial_number = self.position + 1
        num_trials = NUM_TRIALS_PARTICIPANT if self.phase == "experiment" else 2
        return ModularPage(
            "tapping_page",
            AudioPrompt(
                self.origin.target_url,
                Markup(
                    f"""
                    <h3>Imitate the rhythm</h3>
                    Listen to the rhythm and imitate it as best as you can by tapping with your finger.
                    <br><br>
                    <i>Trial number {trial_number} out of {num_trials} trials.</i>
                    """
                ),
            ),
            AudioRecordControl(
                duration=duration_rec_sec + 5,
                s3_bucket=BUCKET_NAME,
                public_read=True,
                show_meter=False,
                controls=False,
                auto_advance=False,
            ),
            time_estimate=duration_rec_sec + 5,
            events={
                "promptStart": Event(is_triggered_by="trialStart", delay=0.5),
                "recordStart": Event(is_triggered_by="promptEnd", delay=0.5),
            },
            progress_display=ProgressDisplay(
                duration=(duration_rec_sec * 2 + 4),
                # show_bar=False,
                stages=[
                    ProgressStage(
                        [0.0, (duration_rec_sec + 1)],
                        "Listen to the rhythm and wait...",
                        "orange",
                    ),
                    ProgressStage(
                        [(duration_rec_sec + 1), (duration_rec_sec * 2 + 3)],
                        "START TAPPING!",
                        "red",
                    ),
                    ProgressStage(
                        [(duration_rec_sec * 2 + 3), (duration_rec_sec * 2 + 3.9)],
                        "Finished recording.",
                        "green",
                    ),
                    ProgressStage(
                        [(duration_rec_sec * 2 + 3.9), (duration_rec_sec * 2 + 4)],
                        "Uploading, please wait...",
                        "orange",
                        persistent=True,
                    ),
                ],
            ),
        )


class CustomNetwork(AudioImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    s3_bucket = BUCKET_NAME


class CustomNode(AudioImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarize_trials(self, trials: list, experiment, participant):
        new_rhythm = [trial.analysis["ioi_new_seed"] for trial in trials]
        return [mean(x) for x in zip(*new_rhythm)]

    def synthesize_target(self, output_file):
        random_seed = self.definition
        stim, _, _ = stimulus.make_stim_from_seed(random_seed)
        self.var.info_stimulus = {
            "duration_rec_sec": len(stim) / config.FS,
            "random_seed": random_seed,
        }
        save_samples_to_file(stim, output_file, config.FS)


class CustomSource(AudioImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        if self.network.phase == "practice":
            config.DURATION_RANGE = [500, 2000]
            ioi_seed = stimulus.make_ioi_seed(config.IS_FIXED_DURATION)
            random_seed = [as_native_type(value) for value in ioi_seed]
            return random_seed
        else:
            config.DURATION_RANGE = [250, 2000]
            ioi_seed = stimulus.make_ioi_seed(config.IS_FIXED_DURATION)
            random_seed = [as_native_type(value) for value in ioi_seed]
            return random_seed


# Timeline
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        REPPTappingCalibration(),  # calibrate tapping
        InfoPage(
            Markup(
                f"""
            <h3>Instructions</h3>
            <hr>
            You will take {NUM_TRIALS_PARTICIPANT} trials. In each trial, you will hear a metronome sound
            playing a rhythm.
            <br><br>
            <b><b>Your goal is to reproduce back the rhythm by tapping on the surface of your laptop</b></b>
            <br><br>
            Please make sure to reproduce the rhythm as accurately as possible.</li>
            <hr>
            Click <b>next</b> to start tapping in rhythm!
            """
            ),
            time_estimate=5,
        ),
        AudioImitationChainTrialMaker(
            id_="trial_maker_iterated_tapping",
            network_class=CustomNetwork,
            trial_class=CustomTrial,
            node_class=CustomNode,
            source_class=CustomSource,
            phase="experiment",
            time_estimate_per_trial=TIME_ESTIMATE_PER_TRIAL,
            chain_type="within",
            num_trials_per_participant=NUM_TRIALS_PARTICIPANT,
            num_iterations_per_chain=NUM_ITERATION_CHAIN,  # only relevant in within chains
            num_chains_per_participant=NUM_CHAINS_PER_PARTICIPANT,  # set to None if chain_type="across"
            num_chains_per_experiment=None,  # set to None if chain_type="within"
            trials_per_node=1,
            balance_across_chains=False,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            propagate_failure=False,
            recruit_mode="num_participants",
            target_num_participants=TOTAL_NUM_PARTICIPANTS,
        ),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
