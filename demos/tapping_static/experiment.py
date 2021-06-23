# non_adapting tapping demo with isochronus tapping and beat synchronization to music

##########################################################################################
# Imports
##########################################################################################
import json
import os

import numpy as np
import tapping_extract as tapping
from flask import Markup
from scipy.io import wavfile

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import download_from_s3, prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import (  # REPPMarkersTest,
    JSONSerializer,
    REPPTappingCalibration,
    REPPVolumeCalibrationMusic,
)
from psynet.timeline import PreDeployRoutine, Timeline, join
from psynet.trial.audio import AudioRecordTrial
from psynet.trial.static import (
    StaticTrial,
    StaticTrialMaker,
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec,
)

##########################################################################################
# Global parameters
##########################################################################################
BUCKET_NAME = "sms-technology"
PARAMS = (
    tapping.params_tech_music
)  # Parameters for isochronus and beat synchronization tasks
FS = 44100

NUM_PARTICIPANTS = 20
DURATION_ESTIMATED_TRIAL = 40

# failing criteria
MIN_RAW_TAPS = 50
MAX_RAW_TAPS = 200


##########################################################################################
# Stimuli
##########################################################################################
def as_native_type(x):
    if type(x).__module__ == np.__name__:
        return x.item()
    return x


def create_metronome_from_onsets(stimulus_name, list_onsets):
    # click = tapping.load_resample_file(fs,params['CLICK_FILENAME'], renormalize=1) # to load from file
    click = tapping.load_click(PARAMS, FS)
    stimulus, stimulus_onsets = tapping.make_stimulus_from_isi(FS, list_onsets, click)
    onsets_played = np.array(stimulus_onsets) > -999  # everything!
    (
        procecssed_audio,
        tt,
        shifted_onsets,
        marker_onsets,
    ) = tapping.add_markers_to_audio_onsets(stimulus, stimulus_onsets, FS, PARAMS)
    duration_rec_sec = len(procecssed_audio) / FS

    info_stimulus = {
        "stimulus_name": stimulus_name,
        "duration_rec_sec": duration_rec_sec,
        "stimulus_onsets": stimulus_onsets,
        "onsets_played": onsets_played,
        "shifted_onsets": shifted_onsets,
        "marker_onsets": marker_onsets,
    }
    info_stimulus = json.dumps(info_stimulus, cls=JSONSerializer)
    return procecssed_audio, info_stimulus


def create_music_from_file(stimulus_name, music_audio_filename, onset_filename):
    stimulus_onsets, onsets_played = tapping.read_music_onsets_from_file(onset_filename)
    onsets_played = np.array(onsets_played)
    stimulus = tapping.load_resample_file(FS, music_audio_filename)
    (
        procecssed_audio,
        tt,
        shifted_onsets,
        marker_onsets,
    ) = tapping.add_markers_to_audio_onsets(stimulus, stimulus_onsets, FS, PARAMS)
    duration_rec_sec = len(procecssed_audio) / FS

    info_stimulus = {
        "stimulus_name": stimulus_name,
        "duration_rec_sec": duration_rec_sec,
        "stimulus_onsets": stimulus_onsets,
        "onsets_played": onsets_played,
        "shifted_onsets": shifted_onsets,
        "marker_onsets": marker_onsets,
    }
    info_stimulus = json.dumps(info_stimulus, cls=JSONSerializer)
    return procecssed_audio, info_stimulus


def save_samples_to_file(samples, filename, fs):
    wavfile.write(filename, rate=fs, data=np.array(samples, dtype=np.float32))


def save_json_to_file(info, filename):
    with open(filename, "w") as file:
        file.write(info)


# Isochronus stimuli
# ISO 800ms
tempo_800_ms = np.repeat(800, 25)  # 30s
tempo_800_ms = [as_native_type(value) for value in tempo_800_ms]

# ISO 600ms
tempo_600_ms = np.repeat(600, 33)  # 30s
tempo_600_ms = [as_native_type(value) for value in tempo_600_ms]

iso_stimulus_onsets = [tempo_800_ms, tempo_600_ms]
iso_stimulus_names = ["iso_800ms", "iso_600ms"]


class StimulusVersionSpecISO(StimulusVersionSpec):
    has_media = True
    media_ext = ""

    @classmethod
    def generate_media(cls, definition, output_path):
        if not (os.path.exists(output_path) and os.path.isdir(output_path)):
            os.mkdir(output_path)
        procecssed_audio, info_stimulus = create_metronome_from_onsets(
            definition["stimulus_name"], definition["list_onsets"]
        )
        save_samples_to_file(procecssed_audio, output_path + "/audio.wav", FS)
        save_json_to_file(info_stimulus, output_path + "/info_stimulus.json")


stimulus_ISO = [
    StimulusSpec(
        definition={},
        version_specs=[
            StimulusVersionSpecISO(
                definition={"stimulus_name": name, "list_onsets": onsets}
            )
        ],
        phase="ISO_tapping",
    )
    for name, onsets in zip(iso_stimulus_names, iso_stimulus_onsets)
]

stimulus_ISO_set = StimulusSet(
    "ISO_tapping", stimulus_ISO, version="v1", s3_bucket=BUCKET_NAME
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
        procecssed_audio, info_stimulus = create_music_from_file(
            definition["stimulus_name"],
            definition["music_audio_filename"],
            definition["onset_filename"],
        )
        save_samples_to_file(procecssed_audio, output_path + "/audio.wav", FS)
        save_json_to_file(info_stimulus, output_path + "/info_stimulus.json")


stimulus_music = [
    StimulusSpec(
        definition={},
        version_specs=[
            CStimulusVersionSpecMusic(
                definition={
                    "stimulus_name": name,
                    "music_audio_filename": os.path.join("music", audio_file),
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


##########################################################################################
# Experiment parts
##########################################################################################
class TapTrialAnalysis(AudioRecordTrial, StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "analysis_trial_metronome"}

    def analyze_recording(self, audio_file: str, output_plot: str):
        temp_file = self.info
        with open(temp_file, "r") as file:
            info_stimulus = json.load(file)

        marker_onsets = info_stimulus["marker_onsets"]
        shifted_onsets = info_stimulus["shifted_onsets"]
        onsets_played = info_stimulus["onsets_played"]

        stimulus_name = info_stimulus["stimulus_name"]
        title_in_graph = "Participant {}".format(self.participant_id)

        tstats, tcontent = tapping.do_all_and_plot(
            audio_filename=audio_file,
            marker_onsets=marker_onsets,
            metronome_all_onsets=shifted_onsets,
            metronome_is_played=onsets_played,
            title_in_graph=title_in_graph,
            output_plot=output_plot,
            params=PARAMS,
        )
        new_tcontent = json.dumps(tcontent, cls=JSONSerializer)
        new_tstats = json.dumps(tstats, cls=JSONSerializer)
        output_results = {"tstats": new_tstats, "tcontent": new_tcontent}

        markers_detected = (
            tstats["marker_onsets"] == tstats["marker_detected"]
        )  # TO DO: make marker plural in new tapping script version
        markers_time_error = tstats["markers_OK"]
        min_raw_taps = tstats["ratio_taps_to_metronomes"] > MIN_RAW_TAPS
        max_raw_taps = tstats["ratio_taps_to_metronomes"] < MAX_RAW_TAPS

        failed = not (
            markers_detected and markers_time_error and min_raw_taps and max_raw_taps
        )
        options = [markers_detected, markers_time_error, min_raw_taps, max_raw_taps]
        reasons = [
            "not all markers detected",
            "markers time error too large",
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
            "stimulus_name": stimulus_name,
        }

    @property  # get info_stimulus stroed in json from s3
    def info(self):
        temp_file = "tmp.json"
        remote_key = os.path.join(
            self.stimulus_version.remote_media_dir,
            self.stimulus_version.media_id + "/info_stimulus.json",
        )
        download_from_s3(temp_file, self.s3_bucket, remote_key)
        return temp_file


class TapTrial(TapTrialAnalysis):
    __mapper_args__ = {"polymorphic_identity": "tap_trial"}

    def show_trial(self, experiment, participant):

        temp_file = self.info
        with open(temp_file, "r") as file:
            info_stimulus = json.load(file)

        duration_rec_sec = info_stimulus["duration_rec_sec"]
        time_last_JS_text_ms = (duration_rec_sec * 1000) - (
            PARAMS["MARKER_END_SLACK"] - 500
        )  # markers end slack - start delay (0.5s)

        return ModularPage(
            "trial_practice_page",
            AudioPrompt(
                self.media_url + "/audio.wav",
                Markup(
                    f"""
                    <br><h3>Tap in time</h3>
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
                start_delay=0.5,
            ),
            AudioRecordControl(
                duration=duration_rec_sec, s3_bucket=BUCKET_NAME, public_read=True
            ),
            time_estimate=DURATION_ESTIMATED_TRIAL,
        )

    @property  # get info_stimulus stroed in json from s3
    def info(self):
        temp_file = "tmp.json"
        remote_key = os.path.join(
            self.stimulus_version.remote_media_dir,
            self.stimulus_version.media_id + "/info_stimulus.json",
        )
        download_from_s3(temp_file, self.stimulus_version.s3_bucket, remote_key)
        return temp_file


class TapTrialISO(TapTrial):
    __mapper_args__ = {"polymorphic_identity": "tap_trial_ISO"}


class TapTrialMusic(TapTrial):
    __mapper_args__ = {"polymorphic_identity": "tap_trial_music"}


##########################################################################################
# Tapping tasks
##########################################################################################
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
        time_estimate_per_trial=DURATION_ESTIMATED_TRIAL,
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
        time_estimate_per_trial=DURATION_ESTIMATED_TRIAL,
        target_num_participants=NUM_PARTICIPANTS,
        recruit_mode="num_participants",
        check_performance_at_end=False,
    ),
)


##########################################################################################
# Experiment
##########################################################################################
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        PreDeployRoutine(  # bucket for the experiment
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
        # REPPMarkersTest(), # pre-screening filtering participants based on recording test (markers)
        REPPTappingCalibration(),  # calibrate tapping
        ISO_tapping,
        music_tapping,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
