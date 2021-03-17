import json
import random

import numpy as np
from flask import Markup

from .modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ColourPrompt,
    ImagePrompt,
    ModularPage,
    NAFCControl,
    PushButtonControl,
    RadioButtonControl,
    TextControl,
)
from .page import InfoPage, UnsuccessfulEndPage
from .timeline import CodeBlock, Module, conditional, join
from .trial.audio import AudioRecordTrial
from .trial.non_adaptive import (
    NonAdaptiveTrial,
    NonAdaptiveTrialMaker,
    StimulusSet,
    StimulusSpec,
)


class VolumeTestControlMusic(AudioMeterControl):
    decay = {"display": 0.1, "high": 0.1, "low": 0.1}
    threshold = {"high": -12, "low": -22}
    grace = {"high": 0.0, "low": 1.5}
    warn_on_clip = True
    msg_duration = {"high": 0.25, "low": 0.25}


class REPPVolumeCalibrationMusic(Module):
    """
    This is a volume calibration test to be used when implementing SMS experiments with music stimuli and REPP. It contains
    a page with general technical requirements of REPP and a volume calibration test with a visual sound meter
    and stimulus customized to help participants find the right volume to use REPP.

    Parameters
    ----------
    label : string, optional
        The label for the REPPVolumeCalibration test, default: "repp_volume_calibration_music".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 10.0.

    min_time_before_submitting : float, optional
        Minimum time to wait (in seconds) while the music plays and the participant cannot submit a response, default: 5.0.

    """

    def __init__(
        self,
        label="repp_volume_calibration_music",
        time_estimate_per_trial: float = 10.0,
        min_time_before_submitting: float = 5.0,
        media_url: str = "https://s3.amazonaws.com/repp-materials",
        filename_audio: str = "calibrate.prepared.wav",
        filename_image: str = "REPP-image_rules.png",
    ):
        self.label = label
        self.events = join(
            InfoPage(
                Markup(
                    f"""
            <h3>Attention</h3>
            <hr>
            <b>Throughout the experiment, it is very important to <b>ONLY</b> use the laptop speakers and be in a silent environment.
            <br><br>
            <i>Please do not use headphones, earphones, external speakers, or wireless devices (unplug or deactivate them now)</i>
            <hr>
            <img style="width:70%" src="{media_url}/{filename_image}"  alt="image_rules">
            """
                ),
                time_estimate=5,
            ),
            ModularPage(
                "volume_test_music",
                AudioPrompt(
                    f"{media_url}/{filename_audio}",
                    Markup(
                        """
                <h3>Volume test</h3>
                <hr>
                <h4>We will begin by calibrating your audio volume:</h4>
                <ol><li>Set the volume in your laptop to approximately 90% of the maximum.</li>
                    <li>A music clip is playing to help you find the right volume in your laptop speakers.</li>
                    <li><b>The sound meter</b> below indicates whether the audio volume is at the right level.</li>
                    <li>If necessairy, turn up the volume on your laptop until the sound meter consistently indicates that
                    the volume is <b style="color:green;">"just right"</b>.
                </ol>
                <hr>
                """
                    ),
                    loop=True,
                    enable_submit_after=min_time_before_submitting,
                ),
                VolumeTestControlMusic(
                    min_time=min_time_before_submitting, calibrate=False
                ),
                time_estimate=time_estimate_per_trial,
            ),
        )
        super().__init__(self.label, self.events)


class VolumeTestControlMarkers(AudioMeterControl):
    decay = {"display": 0.1, "high": 0.1, "low": 0}
    threshold = {"high": -5, "low": -10}
    grace = {"high": 0.2, "low": 1.5}
    warn_on_clip = False
    msg_duration = {"high": 0.25, "low": 0.25}


class REPPVolumeCalibrationMarkers(Module):
    """
    This is a volume calibration test to be used when implementing SMS experiments with metronome sounds and REPP. It contains
    a page with general technical requirements of REPP and it then plays a metronome sound to help participants find the right volume to use REPP.

    Parameters
    ----------
    label : string, optional
        The label for the REPPVolumeCalibration test, default: "repp_volume_calibration_markers".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 10.0.

    min_time_before_submitting : float, optional
        Minimum time to wait (in seconds) while the music plays and the participant cannot submit a response, default: 10.0.

    """

    def __init__(
        self,
        label="repp_volume_calibration_markers",
        time_estimate_per_trial: float = 10.0,
        min_time_before_submitting: float = 5.0,
        media_url: str = "https://s3.amazonaws.com/repp-materials",
        filename_audio: str = "only_markers.wav",
        filename_image: str = "REPP-image_rules.png",
    ):
        self.label = label
        self.events = join(
            InfoPage(
                Markup(
                    f"""
            <h3>Attention</h3>
            <hr>
            <b>Throughout the experiment, it is very important to <b>ONLY</b> use the laptop speakers and be in a silent environment.
            <br><br>
            <i>Please do not use headphones, earphones, external speakers, or wireless devices (unplug or deactivate them now)</i>
            <hr>
            <img style="width:70%" src="{media_url}/{filename_image}"  alt="image_rules">
            """
                ),
                time_estimate=5,
            ),
            ModularPage(
                "volume_test",
                AudioPrompt(
                    f"{media_url}/{filename_audio}",
                    Markup(
                        """
                <h3>Volume test</h3>
                <hr>
                <h4>We will begin by calibrating your audio volume:</h4>
                <ol><li>We are playing a sound similar to the ones you will hear during the experiment.</li>
                    <li>Set the volume in your laptop to approximately 90% of the maximum.</li>
                    <li><strong>The sound meter</strong> below indicates whether the audio volume is at the right level.</li>
                    <li>If necessary, turn up the volume on your laptop until the sound meter consistently indicates that
                    the volume is <strong style="color:green;">"just right"</strong>.</li>
                </ol>
                <b><b>If the sound cannot be properly detected by the sound meter, you will not be able to complete this experiment.</b></b>
                <hr>
                """
                    ),
                    loop=True,
                    enable_submit_after=min_time_before_submitting,
                ),
                VolumeTestControlMarkers(
                    min_time=min_time_before_submitting, calibrate=False
                ),
                time_estimate=time_estimate_per_trial,
            ),
        )
        super().__init__(self.label, self.events)


class TappingTestAudioMeter(AudioMeterControl):
    decay = {"display": 0.1, "high": 0.1, "low": 0}
    threshold = {"high": -12, "low": -20}
    grace = {"high": 0.2, "low": 1.5}
    warn_on_clip = False
    msg_duration = {"high": 0.25, "low": 0.25}


class REPPTappingCalibration(Module):
    """
    This is a tapping calibration test to be used when implementing SMS experiments with REPP.
    It is also containing the main instructions about how to tap using this technology.

    Parameters
    ----------
    label : string, optional
        The label for the REPPTappingCalibration test, default: "repp_tapping_calibration".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 10.0.

    min_time_before_submitting : float, optional
        Minimum time to wait (in seconds) while the music plays and the participant cannot submit a response, default: 5.0.
    """

    def __init__(
        self,
        label="repp_tapping_calibration",
        time_estimate_per_trial: float = 10.0,
        min_time_before_submitting: float = 5.0,
        media_url: str = "https://s3.amazonaws.com/repp-materials",
        filename_image: str = "tapping_instructions.jpg",
    ):
        self.label = label
        self.events = ModularPage(
            self.label,
            Markup(
                f"""
            <h3>You will now practice how to tap on your laptop</h3>
            <b>Please always tap on the surface of your laptop using your index finger (see picture)</b>
            <ul><li>Practice tapping and check that the level of your tapping is <b style="color:green;">"just right"</b>.</li>
                <li><i style="color:red;">Do not tap on the keyboard or tracking pad, and do not tap using your nails or any object</i>.</li>
                <li>If your tapping is <b style="color:red;">"too quiet!"</b>, try tapping louder or on a different location on your laptop.</li>
            </ul>
            <img style="width:70%" src="{media_url}/{filename_image}"  alt="image_rules">
            """
            ),
            TappingTestAudioMeter(min_time=min_time_before_submitting, calibrate=False),
            time_estimate=time_estimate_per_trial,
        )
        super().__init__(self.label, self.events)


class JSONSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return super(JSONSerializer, self).encode(bool(obj))
        else:
            return super(JSONSerializer, self).default(obj)


class REPPMarkersCheck(Module):
    """
    This markers check is used to determine whether participants are using hardware
    and software that meets the technical requirements of REPP, such as
    malfunctioning speakers or microphones, or the use of strong noise-cancellation
    technologies. To make the most out of it, the markers check should be used at the
    beginning of the experiment, after providing general instructions
    with the technical requirements of the experiment. In each trial, the markers check plays
    a test stimulus with six marker sounds. The stimulus is then recorded
    with the laptop’s microphone and analyzed using the REPP's signal processing pipeline.
    During the marker playback time, participants are supposed to remain silent
    (not respond).

    Parameters
    ----------

    label : string, optional
        The label for the markers check, default: "repp_markers_test".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 15.0.

    performance_threshold : int, optional
        The performance threshold, default: 1.

    num_trials : int, optional
        The total number of trials to display, default: 3.


    """

    def __init__(
        self,
        label="repp_markers_test",
        time_estimate_per_trial: float = 15.0,
        performance_threshold: int = 0.6,
        media_url: str = "https://s3.amazonaws.com/repp-materials",
        filename_image: str = "REPP-image_rules.png",
        num_trials: int = 3,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(num_trials, media_url, filename_image),
            self.trial_maker(
                media_url,
                time_estimate_per_trial,
                performance_threshold,
                num_trials,
                self.audio_filenames,
            ),
        )
        super().__init__(self.label, self.events)

    audio_filenames = ["audio1.wav", "audio2.wav", "audio3.wav"]

    def instruction_page(self, num_trials, media_url, filename_image):
        return InfoPage(
            Markup(
                f"""
            <h3>Recording test</h3>
            <hr>
            Now we will test the recording quality of your laptop. In {num_trials} trials, you will be
            asked to remain silent while we play and record a sound.
            <br><br>
            <img style="width:50%" src="{media_url}/{filename_image}"  alt="image_rules">
            <br><br>
            When ready, click <b>next</b> for the recording test and please wait in silence.
            <hr>
            """
            ),
            time_estimate=5,
        )

    def trial_maker(
        self,
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        num_trials: float,
        audio_filenames: list,
    ):
        class MarkersTrialMaker(NonAdaptiveTrialMaker):
            give_end_feedback_passed = False
            performance_check_type = "performance"
            performance_check_threshold = performance_threshold

        return MarkersTrialMaker(
            id_="markers_test",
            trial_class=self.trial(time_estimate_per_trial),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url, audio_filenames),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
        )

    def trial(self, time_estimate: float):
        class RecordMarkersTrial(AudioRecordTrial, NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "markers_test_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "markers_test_trial",
                    AudioPrompt(
                        self.definition["url_audio"],
                        Markup(
                            """
                            <h3>Recording test</h3>
                            <hr>
                            <h4>Please remain silent while we play a sound and record it</h4>
                            """
                        ),
                        prevent_response=False,
                        start_delay=0.5,
                    ),
                    AudioRecordControl(
                        duration=self.definition["duration_sec"],
                        s3_bucket="markers-check-recordings",
                        public_read=False,
                    ),
                    time_estimate=time_estimate,
                )

            def show_feedback(self, experiment, participant):
                if self.failed:
                    return InfoPage(
                        Markup(
                            """
                            <h4>The recording quality of your laptop is not good</h4>
                            This may have many reasons. Please try to do one or more of the following:
                            <ol><li>Increase the volumne of your laptop.</li>
                                <li>Make sure your laptop does not use strong noise cancellation or supression technologies (deactivate them now).</li>
                                <li>Make sure you are in a quiet environment (the experiment will not work with noisy recordings).</li>
                                <li>Do not use headphones, earplugs or wireless devices (unplug them now and use only the laptop speakers).</b></li>
                            </ol>
                            We will try more trials, but <b><b>if the recording quality is not sufficiently good, the experiment will terminate.</b></b>
                            """
                        ),
                        time_estimate=5,
                    )
                else:
                    return InfoPage(
                        Markup(
                            """
                            <h4>The recording quality of your laptop is good</h4>
                            We will try some more trials.
                            To complete the experiment and get the full bonus, you will need to have a good recording quality in all trials.
                            """
                        ),
                        time_estimate=5,
                    )

            def gives_feedback(self, experiment, participant):
                return self.position == 0

            def analyse_recording(self, audio_file: str, output_plot: str):
                import tapping_extract as tapping

                params = (
                    tapping.params_tech_music
                )  # IMPORTANT - NEW PARAMETERS for TAPPING TECHNLOGY

                marker_onsets = self.definition["marker_onsets"]
                shifted_onsets = self.definition["shifted_onsets"]
                onsets_played = self.definition["onsets_played"]
                # TODO
                # duration_sec = self.definition["duration_sec"]

                # analysis
                title_in_graph = "Participant {}".format(self.participant_id)

                tstats, tcontent = tapping.do_all_and_plot(
                    audio_filename=audio_file,
                    marker_onsets=marker_onsets,
                    metronome_all_onsets=shifted_onsets,
                    metronome_is_played=onsets_played,
                    title_in_graph=title_in_graph,
                    output_plot=output_plot,
                    params=params,
                )
                new_tcontent = json.dumps(tcontent, cls=JSONSerializer)
                new_tstats = json.dumps(tstats, cls=JSONSerializer)
                output_results = {"tstats": new_tstats, "tcontent": new_tcontent}
                num_detected_markers = int(tstats["marker_detected"])
                correct_answer = self.definition["correct_answer"]

                return {
                    "failed": correct_answer != num_detected_markers,
                    "num_detected_markers": num_detected_markers,
                    "output_results": output_results,
                }

        return RecordMarkersTrial

    def get_stimulus_set(self, media_url: str, audio_filenames: list):
        return StimulusSet(
            "markers_test",
            [
                StimulusSpec(
                    definition={
                        "stim_name": name,
                        "marker_onsets": [
                            2000.0,
                            2280.0,
                            2510.0,
                            8550.022675736962,
                            8830.022675736962,
                            9060.022675736962,
                        ],
                        "shifted_onsets": [4500.0, 5000.0, 5500.0],
                        "onsets_played": [True, True, True],
                        "duration_sec": 12,
                        "url_audio": f"{media_url}/{name}",
                        "correct_answer": 6,
                    },
                    phase="screening",
                )
                for name in audio_filenames
            ],
        )


class LanguageVocabularyTest(Module):
    """
    This is a basic language vocabulary test supported in five languages (determined by ``language_code``): American English (en-US), German (de-DE), Hindi (hi-IN),
    Brazilian Portuguese (pt-BR), and Spanish (es-ES). In each trial, a spoken word is played in the target
    language and the participant must decide which of the given images in the choice set match
    the spoked word, from a total of four possible images. The materials are the same for all languages.
    The trials are randomly selected from a total pool of 14 trials.

    Parameters
    ----------

    label : string, optional
        The label for the language vocabulary test, default: "language_vocabulary_test".

    language_code : string, optional
        The language code of the target language for the test (en-US, de-DE, hi-IN, pt-BR,sp-SP), default: "en-US".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.

    performance_threshold : int, optional
        The performance threshold, default: 6.

    num_trials : float, optional
        The total number of trials to display, default: 7.


    """

    def __init__(
        self,
        label="language_vocabulary_test",
        language_code: str = "en-US",
        media_url: str = "https://s3.amazonaws.com/langauge-test-materials",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 6,
        num_trials: float = 7,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(),
            self.trial_maker(
                media_url,
                language_code,
                time_estimate_per_trial,
                performance_threshold,
                num_trials,
                self.words,
            ),
        )
        super().__init__(self.label, self.events)

    words = [
        "bell",
        "bird",
        "bow",
        "chair",
        "dog",
        "eye",
        "flower",
        "frog",
        "key",
        "knife",
        "moon",
        "star",
        "sun",
        "turtle",
    ]

    def instruction_page(self):
        return InfoPage(
            Markup(
                """
                <h3>Vocabulary test</h3>
                <p>You will now perform a quick vocabulary test.</p>
                <p>
                    In each trial, you will hear one word and see 4 pictures.
                    Your task is to match each word with the correct picture.
                </p>
                """
            ),
            time_estimate=5,
        )

    def trial_maker(
        self,
        media_url: str,
        language_code: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        num_trials: float,
        words: list,
    ):
        class LanguageVocabularyTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == "correct":
                        score += 1
                passed = score > performance_threshold
                return {"score": score, "passed": passed}

        return LanguageVocabularyTrialMaker(
            id_="language_vocabulary",
            trial_class=self.trial(time_estimate_per_trial),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url, language_code, words),
            time_estimate_per_trial=time_estimate_per_trial,
            max_trials_per_block=num_trials,
            check_performance_at_end=True,
        )

    def trial(self, time_estimate: float):
        class LanguageVocabularyTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "language_vocabulary_trial"}

            def show_trial(self, experiment, participant):
                path_correct = self.definition["url_image_folder"] + "/correct"
                path_wrong1 = self.definition["url_image_folder"] + "/wrong1"
                path_wrong2 = self.definition["url_image_folder"] + "/wrong2"
                path_wrong3 = self.definition["url_image_folder"] + "/wrong3"
                order_list = [0, 1, 2, 3]
                rand_order_list = random.sample(order_list, len(order_list))
                list_path_to_rand = [
                    path_correct,
                    path_wrong1,
                    path_wrong2,
                    path_wrong3,
                ]
                list_choices_to_rand = ["correct", "wrong1", "wrong2", "wrong3"]

                return ModularPage(
                    "language_vocabulary_trial",
                    AudioPrompt(
                        self.definition["url_audio"],
                        "Select the picture that matches the word that you heard.",
                    ),
                    PushButtonControl(
                        [
                            list_choices_to_rand[rand_order_list[0]],
                            list_choices_to_rand[rand_order_list[1]],
                            list_choices_to_rand[rand_order_list[2]],
                            list_choices_to_rand[rand_order_list[3]],
                        ],
                        labels=[
                            f'<img src="{list_path_to_rand[rand_order_list[0]]}.png" alt="notworking" height="65px" width="65px"/>',
                            f'<img src="{list_path_to_rand[rand_order_list[1]]}.png" alt="notworking" height="65px" width="65px"/>',
                            f'<img src="{list_path_to_rand[rand_order_list[2]]}.png" alt="notworking" height="65px" width="65px"/>',
                            f'<img src="{list_path_to_rand[rand_order_list[3]]}.png" alt="notworking" height="65px" width="65px"/>',
                        ],
                        style="min-width: 100px; margin: 10px; background: none; border-color: grey;",
                        arrange_vertically=False,
                    ),
                    time_estimate=time_estimate,
                )

        return LanguageVocabularyTrial

    def get_stimulus_set(self, media_url: str, language_code: str, words: list):
        return StimulusSet(
            "language_vocabulary",
            [
                StimulusSpec(
                    definition={
                        "name": name,
                        "url_audio": f"{media_url}/recordings/{language_code}/{name}.wav",
                        "url_image_folder": f"{media_url}/images/{name}",
                        "media_url": f"{media_url}",
                    },
                    phase="screening",
                )
                for name in words
            ],
        )


class LexTaleTest(Module):
    """
    This is an adapted version (shorter) of the  original LexTale test, which checks participants' English proficiency
    in a lexical decision task: "Lemhöfer, K., & Broersma, M. (2012). Introducing LexTALE: A quick and valid lexical test
    for advanced learners of English. Behavior research methods, 44(2), 325-343". In each trial, a word is presented
    for a short period of time (determined by ``hide_after``) and the participant must decide whether the word is an existing word in English or
    it does not exist. The words are chosen from the original study, which used and validated highly unfrequent
    words in English to make the task very difficult for non-native English speakers. See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the LexTale test, default: "lextale_test".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 2.0.

    performance_threshold : int, optional
        The performance threshold, default: 10.

    hide_after : float, optional
        The time in seconds after the word disappears, default: 1.0.


    num_trials : float, optional
        The total number of trials to display, default: 12.


    """

    def __init__(
        self,
        label="lextale_test",
        time_estimate_per_trial: float = 2.0,
        performance_threshold: int = 10,
        media_url: str = "https://s3.amazonaws.com/lextale-test-materials",
        hide_after: float = 1,
        num_trials: float = 12,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(hide_after, num_trials),
            self.trial_maker(
                media_url,
                time_estimate_per_trial,
                performance_threshold,
                hide_after,
                num_trials,
            ),
        )
        super().__init__(self.label, self.events)

    def instruction_page(self, hide_after, num_trials):
        return InfoPage(
            Markup(
                f"""
            <h3>Lexical decision task</h3>
            <p>In each trial, you will be presented with either an exisitng word in English or a fake word that does not exist.</p>
           <p>
                <b>Your task is to decide whether the word exists not.</b>
                <br><br>Each word will disappear in {hide_after} seconds and you will see a total of {num_trials} words.
            </p>
            """
            ),
            time_estimate=5,
        )

    def trial_maker(
        self,
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        hide_after: float,
        num_trials: float,
    ):
        class LextaleTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {"score": score, "passed": passed}

        return LextaleTrialMaker(
            id_="lextale",
            trial_class=self.trial(time_estimate_per_trial, hide_after),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            max_trials_per_block=num_trials,
            check_performance_at_end=True,
        )

    def trial(self, time_estimate: float, hide_after: float):
        class LextaleTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "lextale_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "lextale_trial",
                    ImagePrompt(
                        self.definition["url"],
                        "Does this word exist?",
                        width="100",
                        height="100px",
                        hide_after=hide_after,
                        margin_bottom="15px",
                        text_align="center",
                    ),
                    NAFCControl(["Yes", "No"], ["yes", "no"]),
                    time_estimate=time_estimate,
                )

        return LextaleTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet(
            "lextale",
            [
                StimulusSpec(
                    definition={
                        "label": label,
                        "correct_answer": correct_answer,
                        "url": f"{media_url}/lextale-{label}.png",
                    },
                    phase="screening",
                )
                for label, correct_answer in [
                    ("1", "yes"),
                    ("2", "yes"),
                    ("3", "yes"),
                    ("4", "yes"),
                    ("5", "yes"),
                    ("6", "yes"),
                    ("7", "yes"),
                    ("8", "no"),
                    ("9", "no"),
                    ("10", "no"),
                    ("11", "no"),
                    ("12", "no"),
                ]
            ],
        )


class AttentionCheck(Module):
    """
    This is an attention check aimed to identify and remove participants who are not paying attention or following
    the instructions. The attention check has 2 pages and researchers can choose whether to display the two pages or not,
    and which information to display in each page. Researchers can also choose the conditions to exclude particiapnts (determined by ``fail_on``).

    Parameters
    ----------
    label : string, optional
        The label of the AttentionCheck check, default: "attention_check".

    pages : int, optional
        Whether to display only the first or both pages. Possible values: 1 and 2. Default: 2.

    fail_on: str, optional
        The condition for the AttentionCheck check to fail.
        Possible values: "attention_check_1", "attention_check_2", "any", "both", and `None`. Here, "any" means both checks have to be passed by the particpant to continue, "both" means one of two checks can fail and the participant can still continue, and `None` means both checks can fail and the participant can still continue. Default: "attention_check_1".

    prompt_1_explanation: str, optional
        The text (including HTML code) to display in the first part of the first paragraph of the first page. Default: "Research on personality has identified characteristic sets of behaviours and cognitive patterns that evolve from biological and enviromental factors. To show that you are paying attention to the experiment, please ignore the question below and select the 'Next' button instead."

    prompt_1_main: str, optional
        The text (including HTML code) to display in the last paragraph of the first page. Default: "As a person, I tend to be competitive, jealous, ambitious, and somewhat impatient."

    prompt_2: str, optional
        The text to display on the second page. Default: "What is your favourite color?".

    attention_check_2_word: str, optional
        The word that the user has to enter on the second page. Default: "attention".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.
    """

    def __init__(
        self,
        label: str = "attention_check",
        pages: int = 2,
        fail_on: str = "attention_check_1",
        prompt_1_explanation: str = """
        Research on personality has identified characteristic sets of behaviours and cognitive patterns that
        evolve from biological and enviromental factors. To show that you are paying attention to the experiment,
        please ignore the question below and select the 'Next' button instead.""",
        prompt_1_main: str = "As a person, I tend to be competitive, jealous, ambitious, and somewhat impatient.",
        prompt_2="What is your favourite color?",
        attention_check_2_word="attention",
        time_estimate_per_trial: float = 5.0,
    ):
        assert pages in [1, 2]
        assert not (pages == 1 and fail_on in ["attention_check_2", "both"])
        assert fail_on in [
            "attention_check_1",
            "attention_check_2",
            "any",
            "both",
            None,
        ]

        self.label = label
        self.pages = pages
        self.fail_on = fail_on
        self.attention_check_2_word = attention_check_2_word

        prompt_1_next_page = f""" Also, you must ignore
        the question asked in the next page, and type "{attention_check_2_word}" in the box.
        <br><br>
        {prompt_1_main}"""
        self.prompt_1_text = (
            f'{prompt_1_explanation}{prompt_1_next_page if self.pages == 2 else ""}'
        )
        self.prompt_2 = prompt_2
        self.events = join(
            ModularPage(
                label="attention_check_1",
                prompt=Markup(f"""{self.prompt_1_text}"""),
                control=RadioButtonControl(
                    [1, 2, 3, 4, 5, 6, 7, 0],
                    [
                        Markup("Completely disagree"),
                        Markup("Strongly disagree"),
                        Markup("Disagree"),
                        Markup("Neutral"),
                        Markup("Agree"),
                        Markup("Strongly agree"),
                        Markup("Completely agree"),
                        Markup("Other"),
                    ],
                    name=self.label,
                    arrange_vertically=True,
                    force_selection=False,
                    show_reset_button="on_selection",
                ),
                time_estimate=time_estimate_per_trial,
            ),
            conditional(
                "exclude_check_1",
                lambda experiment, participant: (
                    participant.answer is not None
                    and self.fail_on in ["attention_check_1", "any"]
                ),
                UnsuccessfulEndPage(failure_tags=["attention_check_1"]),
            ),
            CodeBlock(
                lambda experiment, participant: participant.var.new(
                    "first_check_passed", participant.answer is None
                )
            ),
            conditional(
                "attention_check_2",
                lambda experiment, participant: self.pages == 2,
                ModularPage(
                    label="attention_check_2",
                    prompt=self.prompt_2,
                    control=TextControl(width="300px"),
                    time_estimate=time_estimate_per_trial,
                ),
            ),
            conditional(
                "exclude_check_2",
                lambda experiment, participant: (
                    self.pages == 2
                    and fail_on is not None
                    and participant.answer.lower() != self.attention_check_2_word
                    and (
                        self.fail_on in ["attention_check_2", "any"]
                        or not participant.var.first_check_passed
                    )
                ),
                UnsuccessfulEndPage(failure_tags=["attention_check_2"]),
            ),
        )
        super().__init__(self.label, self.events)


class ColorBlindnessTest(Module):
    """
    The color blindness test checks the participant's ability to perceive
    colours. In each trial an image is presented which contains a number and the
    participant must enter the number that is shown into a text box. The image
    disappears after 3 seconds by default, which can be adjusted by providing a different
    value in the ``hide_after`` parameter.

    Parameters
    ----------

    label : string, optional
        The label for the color blindness test, default: "color_blindness_test".

    media : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/ishihara-eye-test/jpg"

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.

    performance_threshold : int, optional
        The performance threshold, default: 4.

    hide_after : float, optional
        The time in seconds after which the image disappears, default: 3.0.

    """

    def __init__(
        self,
        label="color_blindness_test",
        media_url: str = "https://s3.amazonaws.com/ishihara-eye-test/jpg",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        hide_after: float = 3.0,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(hide_after),
            self.trial_maker(
                media_url, time_estimate_per_trial, performance_threshold, hide_after
            ),
        )
        super().__init__(self.label, self.events)

    def instruction_page(self, hide_after):
        if hide_after is None:
            hidden_instructions = ""
        else:
            hidden_instructions = (
                f"This image will disappear after {hide_after} seconds."
            )
        return InfoPage(
            Markup(
                f"""
            <p>We will now perform a quick test to check your ability to perceive colors.</p>
            <p>
                In each trial, you will be presented with an image that contains a number.
                {hidden_instructions}
                You must enter the number that you see into the text box.
            </p>
            """
            ),
            time_estimate=10,
        )

    def trial_maker(
        self,
        media_url: str,
        time_estimate_per_trial: float,
        performance_threshold: int,
        hide_after: float,
    ):
        class ColorBlindnessTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {"score": score, "passed": passed}

        return ColorBlindnessTrialMaker(
            id_="color_blindness",
            trial_class=self.trial(time_estimate_per_trial, hide_after),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

    def trial(self, time_estimate: float, hide_after: float):
        class ColorBlindnessTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_blindness_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_blindness_trial",
                    ImagePrompt(
                        self.definition["url"],
                        "Write down the number in the image.",
                        width="410px",
                        height="403px",
                        hide_after=hide_after,
                        margin_bottom="15px",
                        text_align="center",
                    ),
                    TextControl(width="100px"),
                    time_estimate=time_estimate,
                )

        return ColorBlindnessTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet(
            "color_blindness",
            [
                StimulusSpec(
                    definition={
                        "label": label,
                        "correct_answer": answer,
                        "url": f"{media_url}/ishihara-{label}.jpg",
                    },
                    phase="screening",
                )
                for label, answer in [
                    ("1", "12"),
                    ("2", "8"),
                    ("3", "29"),
                    ("4", "5"),
                    ("5", "3"),
                    ("6", "15"),
                ]
            ],
        )


class ColorVocabularyTest(Module):
    """
    The color vocabulary test checks the participant's ability to name colours. In each trial, a
    colored box is presented and the participant must choose from a set of colors which color is
    displayed in the box. The colors which are presented can be freely chosen by providing an
    optional ``colors`` parameter. See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color vocabulary test, default: "color_vocabulary_test".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.

    performance_threshold : int, optional
        The performance threshold, default: 4.

    colors : list, optional
        A list of tuples each representing one color option. The tuples are of
        the form ("color-name", [R,G,B]) where R, G, and B are numbers in the
        range of 0 - 255 representing a color in the RGB color system. In each
        trial the colors are presented in random order. Default: the list of the
        six colors "turquoise", "magenta", "granite", "ivory", "maroon", and
        "navy".
    """

    def __init__(
        self,
        label="color_vocabulary_test",
        time_estimate_per_trial: float = 5.0,
        performance_threshold: int = 4,
        colors: list = None,
    ):
        self.label = label
        self.colors = self.colors if colors is None else colors
        self.events = join(
            self.instruction_page(),
            self.trial_maker(
                time_estimate_per_trial, performance_threshold, self.colors
            ),
        )
        super().__init__(self.label, self.events)

    colors = [
        ("turquoise", [174, 72, 56]),
        ("magenta", [300, 100, 50]),
        ("granite", [0, 0, 40]),
        ("ivory", [60, 100, 97]),
        ("maroon", [0, 100, 25]),
        ("navy", [240, 100, 25]),
    ]

    def instruction_page(self):
        return InfoPage(
            Markup(
                """
            <p>We will now perform a quick test to check your ability to name colors.</p>
            <p>
                In each trial, you will be presented with a colored box.
                You must choose which color you see in the box.
            </p>
            """
            ),
            time_estimate=10,
        )

    def trial_maker(
        self, time_estimate_per_trial: float, performance_threshold: int, colors: list
    ):
        class ColorVocabularyTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {"score": score, "passed": passed}

        return ColorVocabularyTrialMaker(
            id_="color_vocabulary",
            trial_class=self.trial(time_estimate_per_trial),
            phase="screening",
            stimulus_set=self.get_stimulus_set(colors),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

    def trial(self, time_estimate: float):
        class ColorVocabularyTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "color_vocabulary_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "color_vocabulary_trial",
                    ColourPrompt(
                        self.definition["target_hsl"],
                        "Which color is shown in the box?",
                        text_align="center",
                    ),
                    PushButtonControl(
                        self.definition["choices"],
                        arrange_vertically=False,
                        style="min-width: 150px; margin: 10px",
                    ),
                    time_estimate=time_estimate,
                )

        return ColorVocabularyTrial

    def get_stimulus_set(self, colors: list):
        stimuli = []
        words = [x[0] for x in colors]
        for (correct_answer, hsl) in colors:
            choices = words.copy()
            random.shuffle(choices)
            definition = {
                "target_hsl": hsl,
                "choices": choices,
                "correct_answer": correct_answer,
            }
            stimuli.append(StimulusSpec(definition=definition, phase="screening"))
        return StimulusSet("color_vocabulary", stimuli)


class HeadphoneCheck(Module):
    """
    The headphone check makes sure that the participant is wearing headphones. In each trial,
    three sounds separated by silences are played and the participent's must judge which sound
    was the softest (quietest). See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color headphone check, default: "headphone_check".

    media : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/headphone-check"

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 7.5.

    performance_threshold : int, optional
        The performance threshold, default: 4.
    """

    def __init__(
        self,
        label="headphone_check",
        media_url: str = "https://s3.amazonaws.com/headphone-check",
        time_estimate_per_trial: float = 7.5,
        performance_threshold: int = 4,
    ):
        self.label = label
        self.events = join(
            self.instruction_page(),
            self.trial_maker(media_url, time_estimate_per_trial, performance_threshold),
        )
        super().__init__(self.label, self.events)

    def instruction_page(self):
        return InfoPage(
            Markup(
                """
            <p>We will now perform a quick test to check that you are wearing headphones.</p>
            <p>
                In each trial, you will hear three sounds separated by silences.
                Your task will be to judge
                <strong>which sound was softest (quietest).</strong>
            </p>
            """
            ),
            time_estimate=10,
        )

    def trial_maker(
        self, media_url: str, time_estimate_per_trial: float, performance_threshold: int
    ):
        class HeadphoneTrialMaker(NonAdaptiveTrialMaker):
            def performance_check(self, experiment, participant, participant_trials):
                """Should return a tuple (score: float, passed: bool)"""
                score = 0
                for trial in participant_trials:
                    if trial.answer == trial.definition["correct_answer"]:
                        score += 1
                passed = score >= performance_threshold
                return {"score": score, "passed": passed}

        return HeadphoneTrialMaker(
            id_="headphone_check_trials",
            trial_class=self.trial(time_estimate_per_trial),
            phase="screening",
            stimulus_set=self.get_stimulus_set(media_url),
            time_estimate_per_trial=time_estimate_per_trial,
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

    def trial(self, time_estimate: float):
        class HeadphoneTrial(NonAdaptiveTrial):
            __mapper_args__ = {"polymorphic_identity": "headphone_trial"}

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "headphone_trial",
                    AudioPrompt(
                        self.definition["url"],
                        "Which sound was softest (quietest) -- 1, 2, or 3?",
                    ),
                    PushButtonControl(["1", "2", "3"]),
                    time_estimate=time_estimate,
                )

        return HeadphoneTrial

    def get_stimulus_set(self, media_url: str):
        return StimulusSet(
            "headphone_check",
            [
                StimulusSpec(
                    definition={
                        "label": label,
                        "correct_answer": answer,
                        "url": f"{media_url}/antiphase_HC_{label}.wav",
                    },
                    phase="screening",
                )
                for label, answer in [
                    ("ISO", "2"),
                    ("IOS", "3"),
                    ("SOI", "1"),
                    ("SIO", "1"),
                    ("OSI", "2"),
                    ("OIS", "3"),
                ]
            ],
        )
