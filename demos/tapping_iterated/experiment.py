# Iterated tapping experiment, adapted from Jacoby & McDermott (2017)

##########################################################################################
#### Imports
##########################################################################################
import json
from math import nan
from statistics import mean

import numpy as np
from flask import Markup
from scipy.io import wavfile
from scipy.io.wavfile import write

import psynet.experiment
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    REPPMarkersCheck,
    REPPTappingCalibration,
    REPPVolumeCalibrationMarkers,
)
from psynet.timeline import PreDeployRoutine, Timeline
from psynet.trial.audio import (
    AudioImitationChainNetwork,
    AudioImitationChainNode,
    AudioImitationChainSource,
    AudioImitationChainTrial,
    AudioImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()

import tapping_extract as tapping

##########################################################################################
#### Global parameters
##########################################################################################
BUCKET_NAME = "iterated-tapping-demo"
PARAMS = tapping.params_tech_iter  # Choose paramaters for this demo (iterated tapping)
FS = 44100

TIME_ESTIMATE_PER_TRIAL = PARAMS["REPEATS"] * 3
CLICK = tapping.load_click(PARAMS, FS)

# failing criteria
PERCENT_BAD_TAPS = 50
MIN_RAW_TAPS = 50
MAX_RAW_TAPS = 200
# within chains
NUM_CHAINS_PER_PARTICIPANT = 2  # set to 4 for real experiments
NUM_ITERATION_CHAIN = 5
NUM_TRIALS_PARTICIPANT = 20
TOTAL_NUM_PARTICIPANTS = 50

##########################################################################################
#### Experiment parts
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
        time_last_JS_text_ms = (duration_rec_sec * 1000) - (
            PARAMS["MARKER_END_SLACK"] - 500
        )  # markers end slack - start delay (0.5s)
        position = self.position + 1

        return ModularPage(
            "tapping_page",
            AudioPrompt(
                self.origin.target_url,
                Markup(
                    f"""
                            <h3>Tap in time with the rhythm</h3>
                            Trial number {position} out of {NUM_TRIALS_PARTICIPANT}  trials.
                            <script>
                            show_message = function(message, color_box) {{
                            document.getElementById("record-active").textContent=message
                            document.getElementById("record-active").style.backgroundColor = color_box
                            }}
                            psynet.response.register_on_ready_routine(function() {{
                            message_to_display=[{{"msg":"WAIT IN SILENCE", "time":10, "color": "pink"}},{{"msg":">>>>>>>> START TAPPING! >>>>>>>>", "time":3150,  "color": "lightgreen"}},{{"msg":"STOP TAPPING!", "time":{time_last_JS_text_ms}, "color": "pink"}}]
                            for (let i=0;i<message_to_display.length;i++) {{
                            setTimeout(function(){{ show_message(message_to_display[i].msg, message_to_display[i].color) }}, message_to_display[i].time); }}   }})
                            </script>
                            """
                ),
                prevent_response=False,
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
        tstats, tcontent, titer = tapping.do_all_and_plot_iterative(
            audio_file,
            info_stimulus["marker_onsets"],
            info_stimulus["shifted_onsets"],
            info_stimulus["shifted_onsets_is_played"],
            title_in_graph,
            output_plot,
            info_stimulus["random_seed"],
            PARAMS,
        )

        new_seed = titer["new_seed"]
        old_seed = titer["old_seed"]
        new_titer = json.dumps(titer, cls=JSONSerializer)
        new_tstats = json.dumps(tstats, cls=JSONSerializer)
        list_new_seed = [as_native_type(value) for value in new_seed]
        list_old_seed = [as_native_type(value) for value in old_seed]

        output_results = {
            "tstats": new_tstats,
            "titer": new_titer,
        }

        markers_detected = (
            tstats["marker_onsets"] == tstats["marker_detected"]
        )  # TO DO: make marker plural in new tapping script version
        markers_time_error = tstats["markers_OK"]
        bad_taps = tstats["percent_of_bad_taps"] < PERCENT_BAD_TAPS
        min_raw_taps = tstats["ratio_taps_to_metronomes"] > MIN_RAW_TAPS
        max_raw_taps = tstats["ratio_taps_to_metronomes"] < MAX_RAW_TAPS

        failed = not (
            markers_detected
            and markers_time_error
            and bad_taps
            and min_raw_taps
            and max_raw_taps
        )
        options = [
            markers_detected,
            markers_time_error,
            bad_taps,
            min_raw_taps,
            max_raw_taps,
        ]
        reasons = [
            "not all markers detected",
            "markers time error too large",
            "too many bad taps",
            "too few detected taps",
            "too many detected taps",
        ]

        if False in options:
            index = options.index(False)
            reason = reasons[index]
        else:
            reason = "all good"

        return {
            "failed": failed,
            "reason": reason,
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

        (
            procecssed_audio,
            tt,
            shifted_onsets,
            marker_onsets,
        ) = tapping.add_markers_to_audio_onsets(stim, stim_onsets, FS, PARAMS)
        shifted_onsets_is_played = np.array(shifted_onsets) > -999  # everything!
        info_stimulus = {
            "duration_rec_sec": len(procecssed_audio) / FS,
            "marker_onsets": [as_native_type(value) for value in marker_onsets],
            "shifted_onsets": [as_native_type(value) for value in shifted_onsets],
            "shifted_onsets_is_played": [
                as_native_type(value) for value in shifted_onsets_is_played
            ],
            "random_seed": random_seed,
        }

        self.var.info_stimulus = info_stimulus
        save_samples_to_file(procecssed_audio, output_file, FS)


class CustomSource(AudioImitationChainSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}

    def generate_seed(self, network, experiment, participant):
        IOIseed_in_ms = tapping.randomize_onsets_from_simplex(
            PARAMS["CLICKS"], PARAMS["TOT"], MIN_RATIO=PARAMS["MIN_RATIO"]
        )
        IOIseed_in_ms = [as_native_type(value) for value in IOIseed_in_ms]

        return IOIseed_in_ms


##########################################################################################
#### Timeline
##########################################################################################
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": "markers-check-recordings",
                "public_read": True,
                "create_new_bucket": True,
            },  # s3 bucket to store markers check recordings
        ),
        REPPVolumeCalibrationMarkers(),  # calibrate volume for markers
        REPPTappingCalibration(),  # calibrate tapping
        # REPPMarkersCheck(), # pre-screening filtering participants based on recording test (markers)
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
