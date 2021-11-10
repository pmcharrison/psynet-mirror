# non_adapting tapping demo with isochronus tapping and beat synchronization to music
import json
import os

import numpy as np
from flask import Markup
from repp.analysis import REPPAnalysis

# repp imports
from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from repp.utils import save_json_to_file, save_samples_to_file

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import download_from_s3, prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (
    JSONSerializer,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import (
    PreDeployRoutine,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    join,
)
from psynet.trial.audio import AudioRecordTrial
from psynet.trial.static import (
    StaticTrial,
    StaticTrialMaker,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec,
)

# Global parameters
BUCKET_NAME = "sms-technology"
NUM_PARTICIPANTS = 20
DURATION_ESTIMATED_TRIAL = 40
NUM_TRIALS_PER_PARTICIPANT = 2
# failing criteria
MIN_RAW_TAPS = 50
MAX_RAW_TAPS = 200


# Stimuli
def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x


def create_iso_stim(stim_name, stim_ioi):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim_onsets = stimulus.make_onsets_from_ioi(stim_ioi)
    stim_prepared, stim_info, _ = stimulus.prepare_stim_from_onsets(stim_onsets)
    info = json.dumps(stim_info, cls=JSONSerializer)
    return stim_prepared, info


def create_music_stim(stim_name, fs, audio_filename, onsets_filename):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim, stim_onsets, onset_is_played = stimulus.load_stimulus_from_files(
        fs, audio_filename, onsets_filename
    )
    stim_prepared, stim_info = stimulus.filter_and_add_markers(
        stim, stim_onsets, onset_is_played
    )
    info = json.dumps(stim_info, cls=JSONSerializer)
    return stim_prepared, info


# Isochronus stimuli
# ISO 800ms
tempo_800_ms = np.repeat(800, 15)
tempo_800_ms = [as_native_type(value) for value in tempo_800_ms]
# ISO 600ms
tempo_600_ms = np.repeat(600, 12)
tempo_600_ms = [as_native_type(value) for value in tempo_600_ms]
# stimuli lists
iso_stimulus_onsets = [tempo_800_ms, tempo_600_ms]
iso_stimulus_names = ["iso_800ms", "iso_600ms"]


class StimulusVersionSpecISO(StimulusVersionSpec):
    has_media = True
    media_ext = ""

    @classmethod
    def generate_media(cls, definition, output_path):
        if not (os.path.exists(output_path) and os.path.isdir(output_path)):
            os.mkdir(output_path)
        stim_prepared, info = create_iso_stim(
            definition["stim_name"], definition["list_iois"]
        )
        save_samples_to_file(stim_prepared, output_path + "/audio.wav", sms_tapping.FS)
        save_json_to_file(info, output_path + "/info.json")


stimulus_iso = [
    StimulusSpec(
        definition={},
        version_specs=[
            StimulusVersionSpecISO(definition={"stim_name": name, "list_iois": iois})
        ],
        phase="ISO_tapping",
    )
    for name, iois in zip(iso_stimulus_names, iso_stimulus_onsets)
]

stimulus_ISO_set = StimulusSet(
    "ISO_tapping", stimulus_iso, version="v1", s3_bucket=BUCKET_NAME
)

# Music stimuli
music_stimulus_name = ["track1", "track2"]
music_audio_names = ["train1.unfiltered.wav", "train7.unfiltered.wav"]
music_text_names = ["train1.unfiltered.txt", "train7.unfiltered.txt"]


class CStimulusVersionSpecMusic(StimulusVersionSpec):
    has_media = True
    media_ext = ""

    @classmethod
    def generate_media(cls, definition, output_path):
        if not (os.path.exists(output_path) and os.path.isdir(output_path)):
            os.mkdir(output_path)
        stim_prepared, info = create_music_stim(
            definition["stim_name"],
            sms_tapping.FS,
            definition["audio_filename"],
            definition["onset_filename"],
        )
        save_samples_to_file(stim_prepared, output_path + "/audio.wav", sms_tapping.FS)
        save_json_to_file(info, output_path + "/info.json")


stimulus_music = [
    StimulusSpec(
        definition={},
        version_specs=[
            CStimulusVersionSpecMusic(
                definition={
                    "stim_name": name,
                    "audio_filename": os.path.join("music", audio_file),
                    "onset_filename": os.path.join("music", onset_file),
                }
            )
        ],
        phase="music_tapping",
    )
    for name, audio_file, onset_file in zip(
        music_stimulus_name, music_audio_names, music_text_names
    )
]

stimulus_music_set = StimulusSet(
    "music_tapping", stimulus_music, version="v1", s3_bucket=BUCKET_NAME
)


# Experiment parts
class TapTrialAnalysis(AudioRecordTrial, StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "analysis_trial_metronome"}

    def analyze_recording(self, audio_file: str, output_plot: str):
        temp_file = self.info
        with open(temp_file, "r") as file:
            info_pre = json.load(file)
            info = json.loads(info_pre)
        stim_name = info["stim_name"]
        title_in_graph = "Participant {}".format(self.participant_id)
        analysis = REPPAnalysis(config=sms_tapping)
        output, analysis, is_failed = analysis.do_analysis(
            info, audio_file, title_in_graph, output_plot
        )
        output = json.dumps(output, cls=JSONSerializer)
        analysis = json.dumps(analysis, cls=JSONSerializer)
        return {
            "failed": is_failed["failed"],
            "reason": is_failed["reason"],
            "output": output,
            "analysis": analysis,
            "stim_name": stim_name,
        }

    @property
    def info(self):
        temp_file = "tmp.json"
        remote_key = os.path.join(
            self.stimulus_version.remote_media_dir,
            self.stimulus_version.media_id + "/info.json",
        )
        download_from_s3(temp_file, self.s3_bucket, remote_key)
        return temp_file


class TapTrial(TapTrialAnalysis):
    __mapper_args__ = {"polymorphic_identity": "tap_trial"}

    def show_trial(self, experiment, participant):
        temp_file = self.info
        with open(temp_file, "r") as file:
            info_pre = json.load(file)
            info = json.loads(info_pre)
        duration_rec = info["stim_duration"]
        trial_number = self.position + 1
        return ModularPage(
            "trial_main_page",
            AudioPrompt(
                self.media_url + "/audio.wav",
                Markup(
                    f"""
                    <br><h3>Tap in time with the metronome.</h3>
                    Trial number {trial_number} out of {NUM_TRIALS_PER_PARTICIPANT}  trials.
                    """
                ),
            ),
            AudioRecordControl(
                duration=duration_rec,
                s3_bucket=BUCKET_NAME,
                public_read=True,
                show_meter=False,
                controls=False,
                auto_advance=False,
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
                    ),
                    ProgressStage(
                        0.5,
                        "Uploading, please wait...",
                        "orange",
                        persistent=True,
                    ),
                ],
            ),
        )

    @property
    def info(self):
        temp_file = "tmp.json"
        remote_key = os.path.join(
            self.stimulus_version.remote_media_dir,
            self.stimulus_version.media_id + "/info.json",
        )
        download_from_s3(temp_file, self.stimulus_version.s3_bucket, remote_key)
        return temp_file


class TapTrialISO(TapTrial):
    __mapper_args__ = {"polymorphic_identity": "tap_trial_ISO"}

    time_estimate = DURATION_ESTIMATED_TRIAL


class TapTrialMusic(TapTrial):
    __mapper_args__ = {"polymorphic_identity": "tap_trial_music"}

    time_estimate = DURATION_ESTIMATED_TRIAL


# Tapping tasks
ISO_tapping = join(
    InfoPage(
        Markup(
            """
            <h3>Tapping to rhythm</h3>
            <hr>
            In each trial, you will hear a metronome sound playing at a constant pace.
            <br><br>
            <b><b>Your goal is to tap in time with the rhythm.</b></b> <br><br>
            <b><b>ATTENTION: </b></b>
            <li>Start tapping as soon as the metronome starts and continue tapping in each metronome click.</li>
            <li>At the beginning and end of each rhythm, you will hear three consequtive beeps.
            <b>Do not tap during these beeps, as they signal the beginning and end of each rhythm.</b></li>
            </ul>
            <hr>
            Click <b>next</b> to start tapping!
            """
        ),
        time_estimate=10,
    ),
    StaticTrialMaker(
        id_="ISO_tapping",
        trial_class=TapTrialISO,
        phase="ISO_tapping",
        stimulus_set=stimulus_ISO_set,
        target_num_participants=NUM_PARTICIPANTS,
        recruit_mode="num_participants",
        check_performance_at_end=False,
    ),
)

music_tapping = join(
    InfoPage(
        Markup(
            """
        <h3>Tapping to music</h3>
        <hr>
        Now you will listen to music.<br><br>
        <b><b>Your goal is to tap in time with the beat of the music until the music ends</b></b><br><br>
        <b><b>The metronome: </b></b>We added a metronome to help you find the
            beat of the music. This metronome will gradually fade out, but you need to keep tapping to
            the beat until the music ends.
        <br><br>
        <img style="width:70%; height:65%;" src="/static/images/example_task.png"  alt="example_task">
        <hr>
        Click <b>next</b> to start tapping to the music!
        """
        ),
        time_estimate=5,
    ),
    StaticTrialMaker(
        id_="music_tapping",
        trial_class=TapTrialMusic,
        phase="music_tapping",
        stimulus_set=stimulus_music_set,
        target_num_participants=NUM_PARTICIPANTS,
        recruit_mode="num_participants",
        check_performance_at_end=False,
    ),
)


# Experiment
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        PreDeployRoutine(
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": BUCKET_NAME,
                "public_read": True,
                "create_new_bucket": True,
            },
        ),
        PreDeployRoutine(  # bucket for REPPMarkersTest
            "prepare_s3_bucket_for_presigned_urls",
            prepare_s3_bucket_for_presigned_urls,
            {
                "bucket_name": "markers-check-recordings",
                "public_read": True,
                "create_new_bucket": True,
            },  # s3 bucket to store markers check recordings
        ),
        REPPVolumeCalibrationMusic(),  # calibrate volume with music
        REPPMarkersTest(),  # pre-screening filtering participants based on recording test (markers)
        REPPTappingCalibration(),  # calibrate tapping
        ISO_tapping,
        music_tapping,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
