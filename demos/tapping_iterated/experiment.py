# Iterated tapping experiment, adapted from Jacoby & McDermott (2017)
import json
from statistics import mean

import numpy as np
from flask import Markup

# repp imports
from repp.config import ConfigUpdater, sms_tapping
from reppextension.iterated_tapping import (
    REPPAnalysisItap,
    REPPStimulusItap,
    make_stim_onsets_from_ioi_seed,
)
from scipy.io import wavfile

import psynet.experiment
from psynet.asset import DebugStorage, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    NumpySerializer,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMarkers,
)
from psynet.timeline import ProgressDisplay, ProgressStage, Timeline
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
config = ConfigUpdater.create_config(
    sms_tapping,
    {
        "LABEL": "iterated tapping",
        "USE_CLICK_FILENAME": True,
        "PLOTS_TO_DISPLAY": [4, 4],
        "INTERVAL_RHYTHM": 3,
        "REPEATS": 10,
        "TOTAL_DURATION": 2000,
        "PROB_NO_CHANGE": 1 / 3,
        "MIN_RATIO": 150.0 / 1000.0,
        "SLACK_RATIO": 0.95,
        "IS_FIXED_DURATION": True,
    },
)
TIME_ESTIMATE_PER_TRIAL = config.REPEATS * 3
stimulus = REPPStimulusItap("itap", config=config)
analysis_itap = REPPAnalysisItap(config=config)


# failing criteria
PERCENT_BAD_TAPS = 50
MIN_RAW_TAPS = 50
MAX_RAW_TAPS = 200
# within chains
NUM_CHAINS_PER_PARTICIPANT = 2  # set to 4 for real experiments
NUM_ITERATION_CHAIN = 5
NUM_TRIALS_PARTICIPANT = 4
TOTAL_NUM_PARTICIPANTS = 50


# Experiment parts
def save_samples_to_file(samples, filename, fs):
    wavfile.write(filename, rate=fs, data=samples.astype(np.float32))


def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x


class CustomTrialAnalysis(AudioImitationChainTrial):
    def analyze_recording(self, audio_file: str, output_plot: str):
        info_stimulus = self.origin.var.info_stimulus
        title_in_graph = "Participant {}".format(self.participant_id)
        output, analysis, is_failed, output_iteration = analysis_itap.do_analysis(
            info_stimulus,
            info_stimulus["random_seed"],
            audio_file,
            title_in_graph,
            output_plot,
        )
        new_seed = output_iteration["new_ioi_seed"]
        old_seed = output_iteration["old_ioi_seed"]
        failed = output_iteration["seed_needs_change"]
        reason = output_iteration["seed_needs_change_reason"]
        ratios_reps = output_iteration["resp_onsets_complete"]
        ratios_reps = json.dumps(ratios_reps, cls=NumpySerializer)
        output_iteration = json.dumps(output_iteration, cls=NumpySerializer)
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
    time_estimate = TIME_ESTIMATE_PER_TRIAL

    def show_trial(self, experiment, participant):
        info_stimulus = self.origin.var.info_stimulus
        duration_rec_sec = info_stimulus["duration_rec"]
        trial_number = self.position + 1
        num_trials = NUM_TRIALS_PARTICIPANT if self.phase == "experiment" else 2
        return ModularPage(
            "tapping_page",
            AudioPrompt(
                self.origin.target_url,
                Markup(
                    f"""
                    <h3>Tap in time with the rhythm</h3>
                    <i>Trial number {trial_number} out of {num_trials} trials.</i>
                    """
                ),
            ),
            AudioRecordControl(
                duration=duration_rec_sec,
                show_meter=False,
                controls=False,
                auto_advance=False,
                bot_response_media="example_trial.wav",
            ),
            time_estimate=duration_rec_sec + 5,
            progress_display=ProgressDisplay(
                show_bar=True,  # set to False to hide progress bar in movement
                stages=[
                    ProgressStage(
                        3.5,
                        "Wait in silence...",
                        "red",
                    ),
                    ProgressStage(
                        [3.5, (duration_rec_sec - 6)],
                        "START TAPPING!",
                        "green",
                    ),
                    ProgressStage(
                        3.5,
                        "Click next when you're ready to continue...",
                        "red",
                        persistent=True,
                    ),
                ],
            ),
        )


class CustomNetwork(AudioImitationChainNetwork):
    pass


class CustomNode(AudioImitationChainNode):
    def summarize_trials(self, trials: list, experiment, participant):
        new_rhythm = [trial.analysis["ioi_new_seed"] for trial in trials]
        return [mean(x) for x in zip(*new_rhythm)]

    def synthesize_target(self, output_file):
        random_seed = self.definition
        stim_onsets = make_stim_onsets_from_ioi_seed(random_seed, config.REPEATS)
        stim, stim_onset_info, _ = stimulus.prepare_stim_from_onsets(stim_onsets)
        info_stimulus = {
            "duration_rec": len(stim) / config.FS,
            "markers_onsets": [
                as_native_type(value) for value in stim_onset_info["markers_onsets"]
            ],
            "stim_shifted_onsets": [
                as_native_type(value)
                for value in stim_onset_info["stim_shifted_onsets"]
            ],
            "onset_is_played": [
                as_native_type(value) for value in stim_onset_info["onset_is_played"]
            ],
            "random_seed": random_seed,
        }
        self.var.info_stimulus = info_stimulus
        save_samples_to_file(stim, output_file, config.FS)


class CustomSource(AudioImitationChainSource):
    def generate_seed(self, network, experiment, participant):
        ioi_seed = stimulus.make_ioi_seed(config.IS_FIXED_DURATION)
        random_seed = [as_native_type(value) for value in ioi_seed]
        return random_seed


class Exp(psynet.experiment.Experiment):
    label = "Iterated tapping demo"
    initial_recruitment_size = 1

    asset_storage = DebugStorage()
    # asset_storage = S3Storage("psynet-demos", "iterated-tapping")

    timeline = Timeline(
        NoConsent(),
        REPPVolumeCalibrationMarkers(),  # calibrate volume for markers
        REPPTappingCalibration(),  # calibrate tapping
        REPPMarkersTest(),  # pre-screening filtering participants based on recording test (markers)
        InfoPage(
            Markup(
                f"""
            <h3>Tapping in rhythm - Instructions</h3>
            <hr>
            You will take {NUM_TRIALS_PARTICIPANT} tapping trials. In each trial, you will hear a metronome sound
            playing a rhythm.
            <br><br>
            <b><b>Your goal is to tap in time to the metronome click</b></b>
            <br><br>
            <b><b>ATTENTION: </b></b>
            <ul><li>Make sure to always tap in synchrony with the metronome.</li>
            <li>Start tapping as soon as the metronome starts and
            continue tapping in each metronome click.</li>
            <li>At the beginning and end of each rhythm, you will hear three consequtive beeps.
                <b>Do not tap during these beeps, as they signal the beginning and end of each rhythm.</b></li>
            </ul>
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
            wait_for_networks=True,
        ),
        SuccessfulEndPage(),
    )
