# Iterated tapping from memory, adapted from Jacoby & McDermott (2017)

##########################################################################################
# Imports
##########################################################################################
import json
from statistics import mean

import numpy as np
import tapping_extract as tapping
from flask import Markup
from scipy.io import wavfile

import psynet.experiment
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import JSONSerializer, REPPTappingCalibration
from psynet.timeline import Timeline
from psynet.trial.audio import (
    AudioImitationChainNetwork,
    AudioImitationChainNode,
    AudioImitationChainSource,
    AudioImitationChainTrial,
    AudioImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# Global parameters
##########################################################################################
BUCKET_NAME = "iterated-tapping-demo"
PARAMS = (
    tapping.params_replication_2int_free_tempo
)  # Choose paramaters for this demo (iterated tapping from memory with 2-interval rhythm)
FS = 44100

TIME_ESTIMATE_PER_TRIAL = PARAMS["REPEATS"] * 3
CLICK = tapping.load_resample_file(
    FS, PARAMS["CLICK_FILENAME"], renormalize=1
)  # to load from file

# failing criteria
MIN_RESPONSES_PLAYED = 5
# within chains
NUM_CHAINS_PER_PARTICIPANT = 2  # set to 4 for a real experiment
NUM_ITERATION_CHAIN = 2  # set to 5 for a real experiment
NUM_TRIALS_PARTICIPANT = 4  # set to 20 for a real experiment
TOTAL_NUM_PARTICIPANTS = 50


##########################################################################################
# Experiment parts
##########################################################################################
def save_samples_to_file(samples, filename, fs):
    wavfile.write(filename, rate=fs, data=samples.astype(np.float32))


def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x


class CustomTrial(AudioImitationChainTrial):
    __mapper_args__ = {"polymorphic_identity": "custom_trial"}

    def show_trial(self, experiment, participant):
        info_stimulus = self.origin.var.info_stimulus
        duration_rec_sec = info_stimulus["duration_rec_sec"]
        # TODO
        # position = self.position + 1

        return ModularPage(
            "tapping_page",
            AudioPrompt(
                self.origin.target_url,
                "Reproduce back the rhythm by tapping on the laptop",
                start_delay=0.5,
            ),
            AudioRecordControl(
                duration=duration_rec_sec, s3_bucket=BUCKET_NAME, public_read=False
            ),
            time_estimate=TIME_ESTIMATE_PER_TRIAL,
        )

    def analyse_recording(self, audio_file: str, output_plot: str):
        info_stimulus = self.origin.var.info_stimulus
        title_in_graph = "tapping extraction"

        tstats, tcontent, titer = tapping.do_all_and_plot_iterative_replication(
            audio_file,
            title_in_graph,
            output_plot,
            info_stimulus["random_seed"],
            PARAMS,
        )

        new_seed = titer["new_seed"]
        old_seed = titer["old_seed"]
        number_of_responses_played = tstats["number_of_responses_played"]
        new_titer = json.dumps(titer, cls=JSONSerializer)

        list_new_seed = [as_native_type(value) for value in new_seed]
        list_old_seed = [as_native_type(value) for value in old_seed]

        output_results = {
            "number_of_responses_played": number_of_responses_played,
            "titer": new_titer,
        }

        failed = not (number_of_responses_played > MIN_RESPONSES_PLAYED)

        return {
            "failed": failed,
            "output_results": output_results,
            "list_new_seed": list_new_seed,
            "list_old_seed": list_old_seed,
        }


class CustomNetwork(AudioImitationChainNetwork):
    __mapper_args__ = {"polymorphic_identity": "custom_network"}

    s3_bucket = BUCKET_NAME


class CustomNode(AudioImitationChainNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}

    def summarise_trials(self, trials: list, experiment, participant):
        new_rhythm = [trial.analysis["list_new_seed"] for trial in trials]
        return [mean(x) for x in zip(*new_rhythm)]

    def synthesise_target(self, output_file):
        random_seed = self.definition
        stim_onsets = tapping.make_stimulus_onsets_from_seed(
            random_seed, repeats=PARAMS["REPEATS"]
        )
        stim = tapping.make_stimulus_from_onsets(FS, stim_onsets, CLICK)

        self.var.info_stimulus = {
            "duration_rec_sec": (1.5 * (1.0 + len(stim) / FS)),
            "random_seed": random_seed,
        }

        save_samples_to_file(stim, output_file, FS)


class CustomSource(AudioImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        if PARAMS["IS_FIXED_DURATION"]:
            IOIseed_in_ms = tapping.randomize_onsets_from_simplex(
                PARAMS["CLICKS"], PARAMS["TOT"], MIN_RATIO=PARAMS["MIN_RATIO"]
            )
        else:
            IOIseed_in_ms = tapping.randomize_onsets_from_simplex_duration_range(
                PARAMS["CLICKS"],
                [PARAMS["MIN_ISI"], PARAMS["MAX_ISI"]],
                MIN_RATIO=PARAMS["MIN_RATIO"],
            )

        IOIseed_in_ms = [as_native_type(value) for value in IOIseed_in_ms]

        return IOIseed_in_ms


##########################################################################################
# Timeline
##########################################################################################
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
            active_balancing_across_chains=False,
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


extra_routes = Exp().extra_routes()
