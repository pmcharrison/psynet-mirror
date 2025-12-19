# imports
import json
import tempfile
import os

from markupsafe import Markup

import psynet.experiment
from psynet.asset import CachedFunctionAsset, LocalStorage
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import ProgressDisplay, ProgressStage, Timeline, join
from psynet.trial.audio import AudioRecordTrial
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

# repp
from repp.analysis import REPPAnalysis
from repp.config import sms_tapping
from reppextension.beat_detection import do_beat_detection_analysis
from psynet.prescreen import REPPMarkersTest, REPPTappingCalibration, REPPVolumeCalibrationMusic


from .utils import (
    NumpySerializer,
    generate_iso_stimulus_audio,
    generate_iso_stimulus_info,
    generate_music_stimulus_audio,
    generate_music_stimulus_info)

########################################################################################################################
# SETUP
########################################################################################################################

# recruitment
NUM_TRIALS_PER_PARTICIPANT = 2
ISO_NUM_TRIALS_PER_PARTICIPANT = 2

# time estimates
DURATION_ESTIMATED_TRIAL = 100

#failing criteria
MIN_RAW_TAPS = 5
MAX_RAW_TAPS = 800

# Config wrapper to include MIN_RAW_TAPS and MAX_RAW_TAPS for beat detection analysis
class ConfigWithThresholds:
    """Wrapper around sms_tapping config that adds MIN_RAW_TAPS and MAX_RAW_TAPS attributes."""
    def __init__(self, base_config):
        # Copy all attributes from base_config
        for attr in dir(base_config):
            if not attr.startswith('_'):
                try:
                    setattr(self, attr, getattr(base_config, attr))
                except AttributeError:
                    pass  # Skip attributes that can't be read
        # Add custom thresholds from experiment settings
        self.MIN_RAW_TAPS = MIN_RAW_TAPS
        self.MAX_RAW_TAPS = MAX_RAW_TAPS

########################################################################################################################
# Stimuli
########################################################################################################################
# Isochronus stimuli
tempo_800_ms = [800] * 15  # ISO 800ms
tempo_600_ms = [600] * 12  # ISO 600ms

iso_stimulus_onsets = [
    tempo_800_ms,
    tempo_600_ms,
]

iso_stimulus_names = [
    "iso_800ms_Trial1",
    "iso_600ms_Trial2",
]


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


# Music stimuli for beat-finding task (no onsets required)
music_folder = "static/music_stimuli"
music_stimulus_audio = [
    os.path.join(music_folder, f)
    for f in os.listdir(music_folder)
    if f.lower().endswith(".wav")
]
music_stimulus_name = [f"track{i+1}" for i in range(len(music_stimulus_audio))]

nodes_music = [
    StaticNode(
        definition={
            "stim_name": name,
            "audio_filename": audio,
        },
        assets={
            "stimulus_audio": CachedFunctionAsset(generate_music_stimulus_audio),
            "stimulus_info": CachedFunctionAsset(generate_music_stimulus_info),
        },
    )
     for name, audio in zip(music_stimulus_name, music_stimulus_audio)
]


########################################################################################################################
# TAPPING ANALYSIS
########################################################################################################################
class TapTrialAnalysisISO(AudioRecordTrial, StaticTrial):

    def get_info(self):
        with tempfile.NamedTemporaryFile() as f:
            self.assets["stimulus_info"].export(f.name)
            with open(f.name, "r") as reader:
                return json.loads(
                    json.load(reader)
                )

    def analyze_recording(self, audio_file: str, output_plot: str):
        info = self.get_info()
        stim_name = info["stim_name"]
        title_in_graph = "Participant {}".format(self.participant_id)

        # Create a config object with MIN_RAW_TAPS and MAX_RAW_TAPS from experiment settings
        analysis = REPPAnalysis(config=sms_tapping)

        # Use beat detection analysis
        # Pass the stimulus info and config to the analysis function
        output, analysis, is_failed = analysis.do_analysis(
            info, audio_file, title_in_graph, output_plot
        )

        # Extract the quality results from is_failed
        is_failed_flag = is_failed.get("failed", True)
        reason = is_failed.get("reason", "Analysis failed")

        extracted_onsets_json = json.dumps(output, cls=NumpySerializer)
        analysis_json = json.dumps(analysis, cls=NumpySerializer)

        return {
            "failed": is_failed_flag,
            "reason": reason,
            "extracted_onsets": extracted_onsets_json,
            "analysis": analysis_json,
            "stim_name": stim_name,
        }


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

        # Create a config object with MIN_RAW_TAPS and MAX_RAW_TAPS from experiment settings
        config = ConfigWithThresholds(sms_tapping)

        # Use beat detection analysis
        # Pass the stimulus info and config to the analysis function
        output, analysis, is_failed = do_beat_detection_analysis(
            audio_file, title_in_graph, output_plot, stim_info=info, config=config, display_zoomed_markers=False)

        # Extract the quality results from is_failed
        is_failed_flag = is_failed.get("failed", True)
        reason = is_failed.get("reason", "Analysis failed")

        extracted_onsets_json = json.dumps(output, cls=NumpySerializer)
        analysis_json = json.dumps(analysis, cls=NumpySerializer)

        return {
            "failed": is_failed_flag,
            "reason": reason,
            "extracted_onsets": extracted_onsets_json,
            "analysis": analysis_json,
            "stim_name": stim_name,
        }


########################################################################################################################
# Experiment parts
########################################################################################################################
def make_progress_display(duration_rec):
    return ProgressDisplay(
        show_bar=True,
        stages=[
            ProgressStage(3.5, "Wait in silence...", "red"),
            ProgressStage([3.5, (duration_rec - 6)], "START TAPPING!", "green"),
            ProgressStage(3.5, "Stop tapping and wait in silence...", "red", persistent=False),
            ProgressStage(0.5, "Press Next when you are ready to continue...", "orange", persistent=True),
        ],
    )


# ------------------ BASE TRIAL ------------------

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
                    <br><h4>Keep your taps simple, steady and evenly spaced. Adjust if the tempo changes.</h4>
                    Trial number {trial_number} out of {NUM_TRIALS_PER_PARTICIPANT} trials.
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
            progress_display=make_progress_display(duration_rec),
        )

    def get_bot_response_media(self):
        raise NotImplementedError


# ------------------ ISO TRIAL ------------------

class TapTrialISO(TapTrialAnalysisISO):
    time_estimate = 15

    def show_trial(self, experiment, participant):
        info = self.get_info()
        duration_rec = info["stim_duration"]
        trial_number = self.position + 1

        return ModularPage(
            "iso_trial_main_page",
            AudioPrompt(
                self.assets["stimulus_audio"].url,
                Markup(
                    f"""
                    <br><h3>Tap in time to the musical beat.</h3>
                    Trial number {trial_number} out of {ISO_NUM_TRIALS_PER_PARTICIPANT} trials.
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
            progress_display=make_progress_display(duration_rec),
        )

    def get_bot_response_media(self):
        return None


# ------------------ MUSIC TRIAL ------------------

class TapTrialMusic(TapTrial):
    time_estimate = DURATION_ESTIMATED_TRIAL

    def get_bot_response_media(self):
        return None


# ------------------ ISO TAPPING TRIAL MAKER ------------------

class ISOTappingTrialMaker(StaticTrialMaker):
    performance_check_type = "score"

    def __init__(
        self,
        id_="ISO_tapping",
        nodes=None,
        n_trials=None,
        performance_threshold: int = 3,
        time_estimate_per_trial: float = 5.0,
    ):
        self.performance_threshold = performance_threshold
        self.time_estimate_per_trial = time_estimate_per_trial

        num_trials = len(nodes) if nodes else n_trials

        super().__init__(
            id_=id_,
            trial_class=TapTrialISO,
            nodes=nodes,
            expected_trials_per_participant=num_trials,
            max_trials_per_participant=num_trials,
            check_performance_at_end=True,
        )

    def performance_check(self, experiment, participant, participant_trials):
        score = sum(
            1 for trial in participant_trials
            if trial.analysis and not trial.analysis.get("failed", True)
        )

        participant.var.set("iso_score", score)

        if self.performance_threshold is None:
            passed = True
        else:
            passed = score >= self.performance_threshold
            if not passed:
                participant.fail()

        participant.var.set("iso_passed", passed)
        return {"score": score, "passed": passed}


# ------------------ TASK DEFINITIONS ------------------

ISO_tapping = join(
    InfoPage(
        Markup(
            """
            <h3>Tapping to Rhythms</h3>
            <hr>
            <p>
            Before the main music trials, you will first practice tapping along with some simple rhythms.
            </p>
            In each trial, you will hear a rhythm at a constant pace.
            <br><br>
            <b>Your goal is to tap in time with the beat of the rhythm.</b><br><br>
            <ul>
                <li>Start tapping as soon as the rhythm starts and continue until it ends.</li>
                <li>The beginning and end include three beeps—don’t tap during these.</li>
            </ul>
            <hr>
            """
        ),
        time_estimate=10,
    ),
    ISOTappingTrialMaker(id_="ISO_tapping", nodes=nodes_iso, performance_threshold=0),
)

music_tapping = join(
    InfoPage(
        Markup(
            """
            <h3>Tapping to Music</h3>
            <hr>
            <p>You will hear several short music excerpts.</p>
            <p><b>Tap along with the music</b> using <b>steady, evenly spaced beats.</b></p>
            <div style="border: 1px solid #ccc; padding: 12px; border-radius: 6px; background-color: #f9f9f9;">
                <ul style="margin: 0; padding-left: 20px;">
                    <li>Keep taps aligned with the general beat.</li>
                    <li>Don’t tap too fast or for every sound.</li>
                    <li>Tap at a natural tempo—like clapping or nodding to music.</li>
                </ul>
            </div>
            <hr>
            <p>There’s no right or wrong—just your personal sense of tempo.</p>
            """
        ),
        time_estimate=5,
    ),
    StaticTrialMaker(
        id_="music_tapping",
        trial_class=TapTrialMusic,
        nodes=nodes_music,
        expected_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
        max_trials_per_participant=NUM_TRIALS_PER_PARTICIPANT,
        check_performance_at_end=False,
    ),
)


########################################################################################################################
# Timeline
########################################################################################################################
class Exp(psynet.experiment.Experiment):
    label = "Music Tapping Experiment Demo"
    asset_storage = LocalStorage()

    timeline = Timeline(
        NoConsent(),
        REPPVolumeCalibrationMusic(),  # calibrate volume with music
        REPPMarkersTest(),  # pre-screening filtering participants based on recording test (markers)
        REPPTappingCalibration(),  # calibrate tapping
        ISO_tapping,
        music_tapping,
        SuccessfulEndPage(),
    )


