# This is a demo showing how to create an static tapping experiment using psynet.
# The demo shows to types of tapping task: isochronus tapping and beat synchronization to music.

import json
import os
import tempfile
from functools import cache

from markupsafe import Markup
from repp.analysis import REPPAnalysis
from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from repp.utils import save_json_to_file, save_samples_to_file

import psynet.experiment
from psynet.asset import CachedFunctionAsset, LocalStorage, S3Storage  # noqa
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    NumpySerializer,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import ProgressDisplay, ProgressStage, Timeline, join
from psynet.trial.audio import AudioRecordTrial
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker


########################################################################################################################
# Global parameters
########################################################################################################################

USE_REPP_PRESCREENS = False # if True, all tapping prescreens are presented before the main tapping tasks, including markers test and volumne calibration


NUM_PARTICIPANTS = 20
DURATION_ESTIMATED_TRIAL = 40
NUM_TRIALS_PER_PARTICIPANT = 2

# failing criteria
MIN_RAW_TAPS = 50
MAX_RAW_TAPS = 200


########################################################################################################################
# Stimuli
########################################################################################################################
# Isochronus stimuli
tempo_800_ms = [800] * 15 # ISO 800ms
tempo_600_ms = [600] * 12 # ISO 600ms

iso_stimulus_onsets = [tempo_800_ms, tempo_600_ms]
iso_stimulus_names = ["iso_800ms", "iso_600ms"]


@cache
def create_iso_stim_with_repp(stim_name, stim_ioi):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim_onsets = stimulus.make_onsets_from_ioi(stim_ioi)
    stim_prepared, stim_info, _ = stimulus.prepare_stim_from_onsets(stim_onsets)
    info = json.dumps(stim_info, cls=NumpySerializer)
    return stim_prepared, info

def generate_iso_stimulus_audio(path, stim_name, list_iois):
    stim_prepared, info = create_iso_stim_with_repp(stim_name, tuple(list_iois))
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)
    
def generate_iso_stimulus_info(path, stim_name, list_iois):
    stim_prepared, info = create_iso_stim_with_repp(stim_name, tuple(list_iois))
    save_json_to_file(info, path)

nodes_iso = [
    StaticNode(
        definition={
            "stim_name": name,
            "list_iois": iois,
        },
        assets={
            "stimulus_audio": CachedFunctionAsset(generate_iso_stimulus_audio),
            "stimulus_info": CachedFunctionAsset(generate_iso_stimulus_info),
        },
    )
    for name, iois in zip(iso_stimulus_names, iso_stimulus_onsets)
]


# Music stimuli
music_stimulus_name = ["track1", "track2"]
music_stimulus_onsets = ["music/train1.unfiltered.txt", "music/train7.unfiltered.txt"]
music_stimulus_audio = ["music/train1.unfiltered.wav", "music/train7.unfiltered.wav"]


@cache
def create_music_stim_with_repp(stim_name, onsets_filename, audio_filename,fs=44100):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim, stim_onsets, onset_is_played = stimulus.load_stimulus_from_files(
        fs, audio_filename, onsets_filename
    )
    stim_prepared, stim_info = stimulus.filter_and_add_markers(
        stim, stim_onsets, onset_is_played
    )
    info = json.dumps(stim_info, cls=NumpySerializer)
    return stim_prepared, info

def generate_music_stimulus_audio(path, stim_name, onsets_filename, audio_filename):
    stim_prepared, _ = create_music_stim_with_repp(stim_name, onsets_filename, audio_filename)
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)
    
def generate_music_stimulus_info(path, stim_name, onsets_filename, audio_filename):
    stim_prepared, info = create_music_stim_with_repp(stim_name, onsets_filename, audio_filename)
    save_json_to_file(info, path)


nodes_music = [
    StaticNode(
        definition={
            "stim_name": name,
            "onsets_filename": iois,
            "audio_filename": audio,
        },
        assets={
            "stimulus_audio": CachedFunctionAsset(generate_music_stimulus_audio),
            "stimulus_info": CachedFunctionAsset(generate_music_stimulus_info),
        },
    )
     for name, iois, audio in zip(music_stimulus_name, music_stimulus_onsets, music_stimulus_audio)
]


########################################################################################################################
# Experiment
########################################################################################################################
class TapTrialAnalysis(AudioRecordTrial, StaticTrial):
    def get_info(self):
        with tempfile.NamedTemporaryFile() as f:
            self.assets["stimulus_info"].export(f.name)
            with open(f.name, "r") as reader:
                return json.loads(
                    json.load(reader)
                )  # For some reason REPP double-JSON-encodes its output

    def analyze_recording(self, audio_file: str, output_plot: str):
        info = self.get_info()
        stim_name = info["stim_name"]
        title_in_graph = "Participant {}".format(self.participant_id)
        analysis = REPPAnalysis(config=sms_tapping)
        output, analysis, is_failed = analysis.do_analysis(
            info, audio_file, title_in_graph, output_plot
        )
        output = json.dumps(output, cls=NumpySerializer)
        analysis = json.dumps(analysis, cls=NumpySerializer)
        return {
            "failed": is_failed["failed"],
            "reason": is_failed["reason"],
            "output": output,
            "analysis": analysis,
            "stim_name": stim_name,
        }


class TapTrial(TapTrialAnalysis):
    def show_trial(self, experiment, participant):
        info = self.get_info()
        duration_rec = info["stim_duration"]
        trial_number = self.position + 1
        return ModularPage(
            "trial_main_page",
            AudioPrompt(
                self.assets["stimulus_audio"].url,
                Markup(
                    f"""
                    <br><h3>Tap in time with the metronome.</h3>
                    Trial number {trial_number} out of {NUM_TRIALS_PER_PARTICIPANT}  trials.
                    """
                ),
            ),
            AudioRecordControl(
                duration=duration_rec,
                show_meter=False,
                controls=False,
                auto_advance=False,
                bot_response_media=self.get_bot_response_media(),
            ),
            time_estimate=duration_rec + 5,
            progress_display=ProgressDisplay(
                show_bar=True,  # set to False to hide progress bar in movement
                stages=[
                    ProgressStage(
                        3.5,
                        "Wait in silence...",
                        "red",
                    ),
                    ProgressStage(
                        [3.5, (duration_rec - 6)],
                        "START TAPPING!",
                        "green",
                    ),
                    ProgressStage(
                        3.5,
                        "Stop tapping and wait in silence...",
                        "red",
                        persistent=False,
                    ),
                    ProgressStage(
                        0.5,
                        "Press Next when you are ready to continue...",
                        "orange",
                        persistent=True,
                    ),
                ],
            ),
        )

    def get_bot_response_media(self):
        raise NotImplementedError


class TapTrialISO(TapTrial):
    time_estimate = DURATION_ESTIMATED_TRIAL

    def get_bot_response_media(self):
        return {
            "iso_800ms": "example_iso_slow_tap.wav",
            "iso_600ms": "example_iso_fast_tap.wav",
        }[self.definition["stim_name"]]


class TapTrialMusic(TapTrial):
    time_estimate = DURATION_ESTIMATED_TRIAL

    def get_bot_response_media(self):
        return {
            "track1": "example_music_tapping_track_1.wav",
            "track2": "example_music_tapping_track_7.wav",
        }[self.definition["stim_name"]]


# Tapping tasks
ISO_tapping = join(
    InfoPage(
        Markup(
            """
            <h3>Tapping to Rhythms</h3>
            <hr>
            In each trial, you will hear a metronome sound playing at a constant pace.
            <br><br>
            <b><b>Your goal is to tap in time with the rhythm.</b></b> <br><br>
            Note:
            <ul>
                <li>Start tapping as soon as the metronome starts and continue tapping in each metronome click.</li>
                <li>At the beginning and end of each rhythm, you will hear three consequtive beeps.</li>
                <li>Do not tap during these beeps, as they signal the beginning and end of each rhythm.</li>
            </ul>
            <br>
            <hr>
            """
        ),
        time_estimate=10,
    ),
    StaticTrialMaker(
        id_="ISO_tapping",
        trial_class=TapTrialISO,
        nodes=nodes_iso,
        expected_trials_per_participant=len(nodes_iso),
        target_n_participants=NUM_PARTICIPANTS,
        recruit_mode="n_participants",
        check_performance_at_end=False,
    ),
)

music_tapping = join(
    InfoPage(
        Markup(
            """
            <h3>Tapping to Music</h3>
            <hr>
            You will now listen to music.
            <br><br>
            <b><b>Your goal is to tap in time with the beat of the music until the music ends.</b></b>
            <br><br>
            <b><b>The metronome:</b></b> We added a metronome to help you find the beat of the music. This metronome will gradually 
            fade out, but you need to keep tapping to the beat until the music ends.
            <br><br>
            <img style="width:50%; height:30%;" src="/static/images/example_task.png"  alt="example_task">
            """
            ),
        time_estimate=5,
    ),
    StaticTrialMaker(
        id_="music_tapping",
        trial_class=TapTrialMusic,
        nodes=nodes_music,
        expected_trials_per_participant=len(nodes_music),
        target_n_participants=NUM_PARTICIPANTS,
        recruit_mode="n_participants",
        check_performance_at_end=False,
    ),
)


########################################################################################################################
# Timeline
########################################################################################################################

class Exp(psynet.experiment.Experiment):
    label = "Tapping (static) demo"
    asset_storage = LocalStorage()

    if USE_REPP_PRESCREENS:
        timeline = Timeline(
            NoConsent(),
            REPPVolumeCalibrationMusic(),  # calibrate volume with music
            REPPMarkersTest(),  # pre-screening filtering participants based on recording test (markers)
            REPPTappingCalibration(),  # calibrate tapping
            ISO_tapping,
            music_tapping,
            SuccessfulEndPage(),
        )
    else:
        timeline = Timeline(
            NoConsent(),
            ISO_tapping,
            music_tapping,
            SuccessfulEndPage(),
        )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
