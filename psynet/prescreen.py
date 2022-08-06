import json
import random
from os.path import exists as file_exists
from random import shuffle
from typing import List, Optional

import numpy as np
import pandas as pd
from flask import Markup

from .asset import ExternalAsset
from .modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ColorPrompt,
    ImagePrompt,
    ModularPage,
    PushButtonControl,
    RadioButtonControl,
    TextControl,
)
from .page import InfoPage, UnsuccessfulEndPage
from .timeline import (
    CodeBlock,
    Event,
    Module,
    PageMaker,
    ProgressDisplay,
    ProgressStage,
    conditional,
    join,
)
from .trial.audio import AudioRecordTrial
from .trial.static import StaticTrial, StaticTrialMaker, Stimulus


class REPPVolumeCalibration(Module):
    def __init__(
        self,
        label,
        materials_url: str = "https://s3.amazonaws.com/repp-materials",
        min_time_on_calibration_page: float = 5.0,
        time_estimate_for_calibration_page: float = 10.0,
    ):
        super().__init__(
            label,
            join(
                self.asset_calibration_audio(materials_url),
                self.asset_rules(materials_url),
                self.introduction(),
                self.volume_calibration(
                    min_time_on_calibration_page,
                    time_estimate_for_calibration_page,
                ),
            ),
        )

    asset_calibration_audio_id = "repp_volume_calibration_audio"

    def asset_calibration_audio(self, materials_url):
        raise NotImplementedError

    asset_rules_id = "repp_image_rules"

    def asset_rules(self, materials_url):
        return ExternalAsset(
            self.asset_rules_id, materials_url + materials_url + "/REPP-image_rules.png"
        )

    def introduction(self):
        return PageMaker(
            lambda assets: InfoPage(
                Markup(
                    f"""
                      <h3>Attention</h3>
                      <hr>
                      <b>Throughout the experiment, it is very important to <b>ONLY</b> use the laptop speakers and be in a silent environment.
                      <br><br>
                      <i>Please do not use headphones, earphones, external speakers, or wireless devices (unplug or deactivate them now)</i>
                      <hr>
                      <img style="width:70%" src="{assets.get('repp_image_rules').url}"  alt="image_rules">
                      """
                ),
            ),
            time_estimate=5,
        )

    def volume_calibration(
        self,
        min_time_on_calibration_page,
        time_estimate_for_calibration_page,
    ):
        return PageMaker(
            lambda assets: ModularPage(
                "volume_test",
                AudioPrompt(
                    assets.get(self.asset_calibration_audio_id),
                    self.calibration_instructions(),
                    loop=True,
                ),
                self.AudioMeter(min_time=min_time_on_calibration_page, calibrate=False),
            ),
            time_estimate=time_estimate_for_calibration_page,
        )

    class AudioMeter(AudioMeterControl):
        pass

    def calibration_instructions(self):
        return Markup(
            f"""
            <h3>Volume test</h3>
            <hr>
            <h4>We will begin by calibrating your audio volume:</h4>
            <ol>
                <li>{self.what_are_we_playing()}</li>
                <li>Set the volume in your laptop to approximately 90% of the maximum.</li>
                <li><b>The sound meter</b> below indicates whether the audio volume is at the right level.</li>
                <li>If necessary, turn up the volume on your laptop until the sound meter consistently indicates that
                the volume is <b style="color:green;">"just right"</b>.
            </ol>
            <hr>
            """
        )

    def what_are_we_playing(self):
        return "A sound is playing to help you find the right volume in your laptop speakers."


class REPPVolumeCalibrationMusic(REPPVolumeCalibration):
    """
    This is a volume calibration test to be used when implementing SMS experiments with music stimuli and REPP. It contains
    a page with general technical requirements of REPP and a volume calibration test with a visual sound meter
    and stimulus customized to help participants find the right volume to use REPP.

    Parameters
    ----------
    label : string, optional
        The label for the REPPVolumeCalibration test, default: "repp_volume_calibration_music".

    materials_url: string
        The location of the REPP materials, default: https://s3.amazonaws.com/repp-materials.

    time_estimate_for_calibration_page : float, optional
        The time estimate for the calibration page, default: 10.0.

    min_time_on_calibration_page : float, optional
        Minimum time (in seconds) that the participant must spend on the calibration page, default: 5.0.

    """

    def __init__(
        self,
        label="repp_volume_calibration_music",
        materials_url: str = "https://s3.amazonaws.com/repp-materials",
        min_time_on_calibration_page: float = 5.0,
        time_estimate_for_calibration_page: float = 10.0,
    ):
        super().__init__(
            label,
            materials_url,
            min_time_on_calibration_page,
            time_estimate_for_calibration_page,
        )

    asset_calibration_audio_id = "repp_volume_calibration_music_audio"

    def asset_calibration(self, materials_url):
        return ExternalAsset(
            self.asset_calibration_audio_id, materials_url + "/calibrate.prepared.wav"
        )

    class AudioMeter(AudioMeterControl):
        decay = {"display": 0.1, "high": 0.1, "low": 0.1}
        threshold = {"high": -12, "low": -22}
        grace = {"high": 0.0, "low": 1.5}
        warn_on_clip = True
        msg_duration = {"high": 0.25, "low": 0.25}

    def what_are_we_playing(self):
        return "A music clip is playing to help you find the right volume in your laptop speakers."


class REPPVolumeCalibrationMarkers(REPPVolumeCalibration):
    """
    This is a volume calibration test to be used when implementing SMS experiments with metronome sounds and REPP. It contains
    a page with general technical requirements of REPP and it then plays a metronome sound to help participants find the right volume to use REPP.

    Parameters
    ----------
    label : string, optional
        The label for the REPPVolumeCalibration test, default: "repp_volume_calibration_music".

    materials_url: string
        The location of the REPP materials, default: https://s3.amazonaws.com/repp-materials.

    time_estimate_for_calibration_page : float, optional
        The time estimate for the calibration page, default: 10.0.

    min_time_on_calibration_page : float, optional
        Minimum time (in seconds) that the participant must spend on the calibration page, default: 5.0.

    """

    def __init__(
        self,
        label="repp_volume_calibration_music",
        materials_url: str = "https://s3.amazonaws.com/repp-materials",
        min_time_on_calibration_page: float = 5.0,
        time_estimate_for_calibration_page: float = 10.0,
    ):
        super().__init__(
            label,
            materials_url,
            min_time_on_calibration_page,
            time_estimate_for_calibration_page,
        )

    asset_calibration_audio_id = "repp_volume_calibration_tapping_audio"

    def asset_calibration(self, materials_url):
        return ExternalAsset(
            self.asset_calibration_audio_id, materials_url + "/only_markers.wav"
        )

    class AudioMeter(AudioMeterControl):
        decay = {"display": 0.1, "high": 0.1, "low": 0}
        threshold = {"high": -5, "low": -10}
        grace = {"high": 0.2, "low": 1.5}
        warn_on_clip = False
        msg_duration = {"high": 0.25, "low": 0.25}

    def what_are_we_playing(self):
        return "We are playing a sound similar to the ones you will hear during the experiment."


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

    materials_url: string
        The location of the REPP materials, default: https://s3.amazonaws.com/repp-materials.
    """

    def __init__(
        self,
        label="repp_tapping_calibration",
        time_estimate_per_trial: float = 10.0,
        min_time_before_submitting: float = 5.0,
        materials_url: str = "https://s3.amazonaws.com/repp-materials",
    ):
        super().__init__(
            label,
            join(
                self.instructions_asset(materials_url),
                PageMaker(
                    lambda assets: ModularPage(
                        label,
                        self.instructions_text(assets),
                        self.AudioMeter(
                            min_time=min_time_before_submitting, calibrate=False
                        ),
                    ),
                    time_estimate=time_estimate_per_trial,
                ),
            ),
        )

    def instructions_asset(self, materials_url):
        return ExternalAsset(
            key="repp_tapping_instructions",
            url=materials_url + "/tapping_instructions.jpg",
        )

    def instructions_text(self, assets):
        return Markup(
            f"""
            <h3>You will now practice how to tap on your laptop</h3>
            <b>Please always tap on the surface of your laptop using your index finger (see picture)</b>
            <ul>
                <li>Practice tapping and check that the level of your tapping is <b style="color:green;">"just right"</b>.</li>
                <li><i style="color:red;">Do not tap on the keyboard or tracking pad, and do not tap using your nails or any object</i>.</li>
                <li>If your tapping is <b style="color:red;">"too quiet!"</b>, try tapping louder or on a different location on your laptop.</li>
            </ul>
            <img style="width:70%" src="{assets.get('repp_tapping_instructions').url}"  alt="image_rules">
            """
        )

    class AudioMeter(AudioMeterControl):
        decay = {"display": 0.1, "high": 0.1, "low": 0}
        threshold = {"high": -12, "low": -20}
        grace = {"high": 0.2, "low": 1.5}
        warn_on_clip = False
        msg_duration = {"high": 0.25, "low": 0.25}


class NumpySerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return super().encode(bool(obj))
        else:
            return super().default(obj)


class FreeTappingRecordTest(Module):
    """
    This pre-screening test is designed to quickly determine whether participants
    are able to provide valid tapping data. The task is also efficient in determining whether
    participants are following the instructions and use hardware
    and software that meets the technical requirements of REPP.
    To make the most out of it, the test should be used at the
    beginning of the experiment, after providing general instructions.
    This test is intended for unconstrained tapping experiments, where no markers are used.
    By default, we start with a warming up exercise where participants can hear their recording.
    We then perform a test with two trials and exclude participants who fail more than once.
    After the first trial, we provide feedback based on the number of detected taps. The only
    exclusion criterion to fail trials is based on the number of detected taps, by default set to
    a minimum of 3 taps. NOTE: this test should be given after a volume and a tapping calibration test.

    Parameters
    ----------

    label : string, optional
        The label for the test, default: "free_tapping_record_test".

    performance_threshold : int, optional
        The performance threshold, default: 0.6.

    duration_rec_sec : float, optional
        Length of the recording, default: 8 sec.

    min_num_detected_taps : float, optional
        Mininum number of detected taps to pass the test, default: 1.

    num_repeat_trials : float, optional
        Number of trials to repeat in the trial maker, default: 0.

    """

    def __init__(
        self,
        label="free_tapping_record_test",
        performance_threshold: int = 0.5,
        duration_rec_sec: int = 8,
        min_num_detected_taps: int = 3,
        num_repeat_trials: int = 1,
    ):
        self.label = label
        self.elts = join(
            self.familiarization_phase(),
            self.trial_maker(
                performance_threshold,
                duration_rec_sec,
                min_num_detected_taps,
                num_repeat_trials,
            ),
        )
        super().__init__(self.label, self.elts)

    def familiarization_phase(self):
        return join(
            InfoPage(
                Markup(
                    """
                    <h3>Warming up</h3>
                    <hr>
                    We will now warm up with a short tapping exercise. On the next page,
                    please tap a steady beat in any tempo that you like.
                    <br><br>
                    <b><b>Attention:</b></b> Tap with your index finger and only tap on the surface of your laptop.</b></b>
                    <hr>
                    """
                ),
                time_estimate=3,
            ),
            ModularPage(
                "free_record_example",
                Markup(
                    """
                    <h4>Tap a steady beat</h4>
                    """
                ),
                AudioRecordControl(
                    duration=7.0,
                    show_meter=True,
                    controls=False,
                    auto_advance=False,
                ),
                time_estimate=5,
                progress_display=ProgressDisplay(
                    stages=[
                        ProgressStage(7, "Recording.. Start tapping!", "red"),
                    ],
                ),
            ),
            PageMaker(
                lambda participant: ModularPage(
                    "playback",
                    AudioPrompt(
                        participant.answer["url"],
                        Markup(
                            """
                        <h3>Can you hear your recording?</h3>
                        <hr>
                        If you do not hear your recording, please make sure
                        your laptop microphone is working and you are not using any headphones or wireless devices.<br><br>
                        <b><b>To proceed, we need to be able to record your tapping.</b></b>
                        <hr>
                        """
                        ),
                    ),
                ),
                time_estimate=5,
            ),
            InfoPage(
                Markup(
                    """
                    <h3>Tapping test</h3>
                    <hr>
                    <b><b>Be careful:</b></b> This is a recording test!<br><br>
                    On the next page, we will ask you again to tap a steady beat in any tempo that you like.
                    <br><br>
                    We will test if we can record your tapping signal properly:
                    <b><b>If we cannot record it, the experiment will terminate here.</b></b>
                    <hr>
                    """
                ),
                time_estimate=3,
            ),
        )

    def trial_maker(
        self,
        performance_threshold: int,
        duration_rec_sec: int,
        min_num_detected_taps: int,
        num_repeat_trials: int,
    ):
        class FreeTappingRecordTrialMaker(StaticTrialMaker):
            performance_check_type = "performance"
            performance_check_threshold = performance_threshold
            give_end_feedback_passed = False

        return FreeTappingRecordTrialMaker(
            id_="free_tapping_record_trialmaker",
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(duration_rec_sec, min_num_detected_taps),
            num_repeat_trials=num_repeat_trials,
            fail_trials_on_premature_exit=False,
            fail_trials_on_participant_performance_check=False,
            check_performance_at_end=True,
        )

    def get_stimulus_set(self, duration_rec_sec: float, min_num_detected_taps: int):
        return [
            Stimulus(
                definition={
                    "duration_rec_sec": duration_rec_sec,
                    "min_num_detected_taps": min_num_detected_taps,
                    "url_audio": "https://s3.amazonaws.com/repp-materials/silence_1s.wav",  # Redundant but keeping for back-compatibility
                },
                assets={
                    "stimulus": ExternalAsset(
                        "repp_silence_1s",
                        "https://s3.amazonaws.com/repp-materials/silence_1s.wav",
                    ),
                },
            )
        ]

    class FreeTappingRecordTrial(AudioRecordTrial, StaticTrial):
        time_estimate = 10

        def show_trial(self, experiment, participant):
            return ModularPage(
                "free_tapping_record",
                AudioPrompt(
                    self.definition["url_audio"],
                    Markup(
                        """
                        <h4>Tap a steady beat</h4>
                        """
                    ),
                ),
                AudioRecordControl(
                    duration=self.definition["duration_rec_sec"],
                    show_meter=False,
                    controls=False,
                    auto_advance=False,
                ),
                time_estimate=self.time_estimate,
                progress_display=ProgressDisplay(
                    stages=[
                        ProgressStage(
                            self.definition["duration_rec_sec"],
                            "Recording... Start tapping!",
                            "red",
                            persistent=True,
                        ),
                    ],
                ),
            )

        def analyze_recording(self, audio_file: str, output_plot: str):
            from repp.analysis import REPPAnalysis
            from repp.config import sms_tapping

            plot_title = "Participant {}".format(self.participant_id)
            repp_analysis = REPPAnalysis(config=sms_tapping)
            _, _, stats = repp_analysis.do_analysis_tapping_only(
                audio_file, plot_title, output_plot
            )
            # output
            num_resp_onsets_detected = stats["num_resp_onsets_detected"]
            min_responses_ok = (
                num_resp_onsets_detected > self.definition["min_num_detected_taps"]
            )
            median_ok = stats["median_ioi"] != 9999
            failed = not (min_responses_ok and median_ok)
            stats = json.dumps(stats, cls=NumpySerializer)
            return {
                "failed": failed,
                "stats": stats,
                "num_resp_onsets_detected": num_resp_onsets_detected,
            }

        def gives_feedback(self, experiment, participant):
            return self.position == 0

        def show_feedback(self, experiment, participant):
            output_analysis = json.loads(self.details["analysis"])
            num_resp_onsets_detected = output_analysis["num_resp_onsets_detected"]

            if self.failed:
                return InfoPage(
                    Markup(
                        f"""
                        <h4>Your tapping was bad...</h4>
                        We detected {num_resp_onsets_detected} taps in the recording. This is not sufficient for this task.
                        Please try to do one or more of the following:
                        <ol><li>Tap a steady beat, providing at least 5-10 taps.</li>
                            <li>Make sure your laptop microphone is working and you are not using headphones or earplugs.</li>
                            <li>Tap on the surface of your laptop using your index finger.</li>
                            <li>Make sure you are in a quiet environment (the experiment will not work with noisy recordings).</li>
                        </ol>
                        <b><b>If we cannot detect your tapping signal in the recording, the experiment will terminate.</b></b>
                        """
                    ),
                    time_estimate=5,
                )
            else:
                return InfoPage(
                    Markup(
                        f"""
                        <h4>Good!</h4>
                        We could detect {num_resp_onsets_detected} taps in the recording.
                        """
                    ),
                    time_estimate=5,
                )

    trial_class = FreeTappingRecordTrial


class REPPMarkersTest(Module):
    """
    This markers test is used to determine whether participants are using hardware
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

    performance_threshold : int, optional
        The performance threshold, default: 1.

    num_trials : int, optional
        The total number of trials to display, default: 3.


    """

    def __init__(
        self,
        label="repp_markers_test",
        performance_threshold: int = 0.6,
        materials_url: str = "https://s3.amazonaws.com/repp-materials",
        num_trials: int = 3,
    ):
        audio_assets = [
            ExternalAsset(
                key=f"repp_markers_test_audio_{i + 1}",
                url=f"{materials_url}/audio{i + 1}.wav",
                label=f"audio{i + 1}.wav",
            )
            for i in range(3)
        ]
        image_asset = ExternalAsset(
            key="repp_rules_image.png",
            url=f"{materials_url}/REPP-image_rules.png",
        )

        self.label = label
        self.elts = join(
            audio_assets,
            image_asset,
            self.instruction_page(num_trials, image_asset),
            self.trial_maker(
                audio_assets,
                performance_threshold,
                num_trials,
            ),
        )
        super().__init__(self.label, self.elts)

    def instruction_page(self, num_trials, image_asset):
        return InfoPage(
            Markup(
                f"""
            <h3>Recording test</h3>
            <hr>
            Now we will test the recording quality of your laptop. In {num_trials} trials, you will be
            asked to remain silent while we play and record a sound.
            <br><br>
            <img style="width:50%" src="{image_asset.url}"  alt="image_rules">
            <br><br>
            When ready, click <b>next</b> for the recording test and please wait in silence.
            <hr>
            """
            ),
            time_estimate=5,
        )

    def trial_maker(
        self,
        audio_assets,
        performance_threshold: int,
        num_trials: float,
    ):
        class MarkersTrialMaker(StaticTrialMaker):
            give_end_feedback_passed = False
            performance_check_type = "performance"
            performance_check_threshold = performance_threshold

        return MarkersTrialMaker(
            id_="markers_test",
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(audio_assets),
            check_performance_at_end=True,
        )

    def get_stimulus_set(self, audio_assets):
        return [
            Stimulus(
                definition={
                    "stim_name": asset.label,
                    "markers_onsets": [
                        2000.0,
                        2280.0,
                        2510.0,
                        8550.022675736962,
                        8830.022675736962,
                        9060.022675736962,
                    ],
                    "stim_shifted_onsets": [4500.0, 5000.0, 5500.0],
                    "onset_is_played": [True, True, True],
                    "duration_sec": 12,
                    "url_audio": asset.url,  # redundant but keeping for back-compatibility
                    "correct_answer": 6,
                },
                assets={
                    "stimulus": asset,
                },
            )
            for asset in audio_assets
        ]

    class RecordMarkersTrial(AudioRecordTrial, StaticTrial):
        time_estimate = 12

        def show_trial(self, experiment, participant):
            return ModularPage(
                "markers_test_trial",
                AudioPrompt(
                    self.stimulus.assets["stimulus"].url,
                    Markup(
                        """
                        <h3>Recording test</h3>
                        <hr>
                        <h4>Please remain silent while we play a sound and record it</h4>
                        """
                    ),
                ),
                AudioRecordControl(
                    duration=self.definition["duration_sec"],
                    show_meter=False,
                    controls=False,
                    auto_advance=False,
                ),
                time_estimate=self.time_estimate,
                progress_display=ProgressDisplay(
                    # show_bar=False,
                    stages=[
                        ProgressStage(11.5, "Recording...", "red"),
                        ProgressStage(
                            0.5,
                            "Click next when you are ready to continue...",
                            "orange",
                            persistent=True,
                        ),
                    ],
                ),
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

        def analyze_recording(self, audio_file: str, output_plot: str):
            from repp.analysis import REPPAnalysis
            from repp.config import sms_tapping

            info = {
                "markers_onsets": self.definition["markers_onsets"],
                "stim_shifted_onsets": self.definition["stim_shifted_onsets"],
                "onset_is_played": self.definition["onset_is_played"],
            }

            title_in_graph = "Participant {}".format(self.participant_id)
            analysis = REPPAnalysis(config=sms_tapping)
            output, analysis, is_failed = analysis.do_analysis(
                info, audio_file, title_in_graph, output_plot
            )
            num_markers_detected = int(analysis["num_markers_detected"])
            correct_answer = self.definition["correct_answer"]

            output = json.dumps(output, cls=NumpySerializer)
            analysis = json.dumps(analysis, cls=NumpySerializer)
            return {
                "failed": correct_answer != num_markers_detected,
                "num_detected_markers": num_markers_detected,
                "output": output,
                "analysis": analysis,
            }

    trial_class = RecordMarkersTrial


class LanguageVocabularyTest(StaticTrialMaker):
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
        num_trials: int = 7,
    ):
        self.introduction = join(
            ExternalAsset(
                "language_test_materials",
                media_url,
                is_folder=True,
            ),
            self.instruction_page(),
        )
        self.time_estimate_per_trial = time_estimate_per_trial
        self.performance_threshold = performance_threshold

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(media_url, language_code, self.words),
            max_trials_per_block=num_trials,
            check_performance_at_end=True,
        )

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

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == "correct":
                score += 1
        passed = score > self.performance_threshold
        return {"score": score, "passed": passed}

    def get_stimulus_set(self, media_url: str, language_code: str, words: list):
        return [
            Stimulus(
                definition={
                    "name": name,
                    "url_audio": f"{media_url}/recordings/{language_code}/{name}.wav",
                    "url_image_folder": f"{media_url}/images/{name}",
                    "media_url": f"{media_url}",
                },
            )
            for name in words
        ]

    class LanguageVocabularyTrial(StaticTrial):
        time_estimate = None

        def show_trial(self, experiment, participant):
            path_correct = self.definition["url_image_folder"] + "/correct"
            path_wrong1 = self.definition["url_image_folder"] + "/wrong1"
            path_wrong2 = self.definition["url_image_folder"] + "/wrong2"
            path_wrong3 = self.definition["url_image_folder"] + "/wrong3"
            order_list = [0, 1, 2, 3]

            # Todo - update this. It is not good practice to call random functions
            # within show_trial, as they will produce different values on page refresh.
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
                    choices=[list_choices_to_rand[x] for x in rand_order_list],
                    labels=[
                        f'<img src="{list_path_to_rand[x]}.png" alt="notworking" height="65px" width="65px"/>'
                        for x in rand_order_list
                    ],
                    style="min-width: 100px; margin: 10px; background: none; border-color: grey;",
                    arrange_vertically=False,
                ),
            )

    trial_class = LanguageVocabularyTrial


class LexTaleTest(StaticTrialMaker):
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
        The performance threshold, default: 8.

    hide_after : float, optional
        The time in seconds after the word disappears, default: 1.0.

    num_trials : float, optional
        The total number of trials to display, default: 12.
    """

    def __init__(
        self,
        label="lextale_test",
        time_estimate_per_trial: float = 2.0,
        performance_threshold: int = 8,
        media_url: str = "https://s3.amazonaws.com/lextale-test-materials",
        hide_after: float = 1,
        num_trials: int = 12,
    ):
        self.hide_after = hide_after
        self.time_estimate_per_trial = time_estimate_per_trial
        self.performance_threshold = performance_threshold
        self.introduction = (self.instruction_page(hide_after, num_trials),)

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(media_url),
            max_trials_per_block=num_trials,
            check_performance_at_end=True,
        )

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

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == trial.definition["correct_answer"]:
                score += 1
        passed = score >= self.performance_threshold
        return {"score": score, "passed": passed}

    def get_stimulus_set(self, media_url: str):
        return [
            Stimulus(
                definition={
                    "label": label,
                    "correct_answer": correct_answer,
                    "url": f"{media_url}/lextale-{label}.png",  # Redundant but kept for back-compatibility
                },
                assets={
                    "word": ExternalAsset(
                        f"lextale_{label}_image",
                        url=f"{media_url}/lextale-{label}.png",
                    )
                },
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
        ]

    class LextaleTrial(StaticTrial):
        time_estimate = 2.0
        hide_after = 1.0

        def show_trial(self, experiment, participant):
            return ModularPage(
                "lextale_trial",
                ImagePrompt(
                    self.stimulus.assets["word"].url,
                    "Does this word exist?",
                    width="100px",
                    height="100px",
                    hide_after=self.hide_after,
                    margin_bottom="15px",
                    text_align="center",
                ),
                PushButtonControl(
                    ["yes", "no"],
                    ["yes", "no"],
                    arrange_vertically=False,
                    style="min-width: 150px; margin: 10px",
                ),
                bot_response=lambda: self.definition["correct_answer"],
            )

    trial_class = LextaleTrial


class AttentionTest(Module):
    """
    This is an attention test aimed to identify and remove participants who are not paying attention or following
    the instructions. The attention test has 2 pages and researchers can choose whether to display the two pages or not,
    and which information to display in each page. Researchers can also choose the conditions to exclude particiapnts (determined by ``fail_on``).

    Parameters
    ----------
    label : string, optional
        The label of the AttentionTest module, default: "attention_test".

    pages : int, optional
        Whether to display only the first or both pages. Possible values: 1 and 2. Default: 2.

    fail_on: str, optional
        The condition for the AttentionTest check to fail.
        Possible values: "attention_test_1", "attention_test_2", "any", "both", and `None`. Here, "any" means both checks have to be passed by the particpant to continue, "both" means one of two checks can fail and the participant can still continue, and `None` means both checks can fail and the participant can still continue. Default: "attention_test_1".

    prompt_1_explanation: str, optional
        The text (including HTML code) to display in the first part of the first paragraph of the first page. Default: "Research on personality has identified characteristic sets of behaviours and cognitive patterns that evolve from biological and enviromental factors. To show that you are paying attention to the experiment, please ignore the question below and select the 'Next' button instead."

    prompt_1_main: str, optional
        The text (including HTML code) to display in the last paragraph of the first page. Default: "As a person, I tend to be competitive, jealous, ambitious, and somewhat impatient."

    prompt_2: str, optional
        The text to display on the second page. Default: "What is your favourite color?".

    attention_test_2_word: str, optional
        The word that the user has to enter on the second page. Default: "attention".

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 5.0.
    """

    def __init__(
        self,
        label: str = "attention_test",
        pages: int = 2,
        fail_on: str = "attention_test_1",
        prompt_1_explanation: str = """
        Research on personality has identified characteristic sets of behaviours and cognitive patterns that
        evolve from biological and enviromental factors. To show that you are paying attention to the experiment,
        please ignore the question below and select the 'Next' button instead.""",
        prompt_1_main: str = "As a person, I tend to be competitive, jealous, ambitious, and somewhat impatient.",
        prompt_2="What is your favourite color?",
        attention_test_2_word="attention",
        time_estimate_per_trial: float = 5.0,
    ):
        assert pages in [1, 2]
        assert not (pages == 1 and fail_on in ["attention_test_2", "both"])
        assert fail_on in [
            "attention_test_1",
            "attention_test_2",
            "any",
            "both",
            None,
        ]

        self.label = label
        self.pages = pages
        self.fail_on = fail_on
        self.attention_test_2_word = attention_test_2_word

        prompt_1_next_page = f""" Also, you must ignore
        the question asked in the next page, and type "{attention_test_2_word}" in the box.
        <br><br>
        {prompt_1_main}"""
        self.prompt_1_text = (
            f'{prompt_1_explanation}{prompt_1_next_page if self.pages == 2 else ""}'
        )
        self.prompt_2 = prompt_2
        self.elts = join(
            ModularPage(
                label="attention_test_1",
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
                bot_response=lambda: None,
            ),
            conditional(
                "exclude_check_1",
                lambda experiment, participant: (
                    participant.answer is not None
                    and self.fail_on in ["attention_test_1", "any"]
                ),
                UnsuccessfulEndPage(failure_tags=["attention_test_1"]),
            ),
            CodeBlock(
                lambda experiment, participant: participant.var.new(
                    "first_check_passed", participant.answer is None
                )
            ),
            conditional(
                "attention_test_2",
                lambda experiment, participant: self.pages == 2,
                ModularPage(
                    label="attention_test_2",
                    prompt=self.prompt_2,
                    control=TextControl(width="300px"),
                    time_estimate=time_estimate_per_trial,
                    bot_response=lambda: self.attention_test_2_word,
                ),
            ),
            conditional(
                "exclude_check_2",
                lambda experiment, participant: (
                    self.pages == 2
                    and fail_on is not None
                    and participant.answer.lower() != self.attention_test_2_word
                    and (
                        self.fail_on in ["attention_test_2", "any"]
                        or not participant.var.first_check_passed
                    )
                ),
                UnsuccessfulEndPage(failure_tags=["attention_test_2"]),
            ),
        )
        super().__init__(self.label, self.elts)


class ColorBlindnessTest(StaticTrialMaker):
    """
    The color blindness test checks the participant's ability to perceive
    colors. In each trial an image is presented which contains a number and the
    participant must enter the number that is shown into a text box. The image
    disappears after 3 seconds by default, which can be adjusted by providing a different
    value in the ``hide_after`` parameter.

    Parameters
    ----------

    label : string, optional
        The label for the color blindness test, default: "color_blindness_test".

    media_url : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/ishihara-eye-test/jpg"

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
        self.hide_after = hide_after
        self.time_estimate_per_trial = time_estimate_per_trial
        self.performance_threshold = performance_threshold

        self.introduction = self.instruction_page(self.hide_after)

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(media_url),
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

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

    def get_stimulus_set(self, media_url: str):
        return [
            Stimulus(
                definition={
                    "label": label,
                    "correct_answer": answer,
                    "url": f"{media_url}/ishihara-{label}.jpg",  # Redundant but kept for back-compatibility
                },
                assets={
                    "image": ExternalAsset(
                        f"ishihara-{label}",
                        url=f"{media_url}/ishihara-{label}.jpg",
                    )
                },
            )
            for label, answer in [
                ("1", "12"),
                ("2", "8"),
                ("3", "29"),
                ("4", "5"),
                ("5", "3"),
                ("6", "15"),
            ]
        ]

    class ColorBlindnessTrial(StaticTrial):
        time_estimate = 5.0

        def show_trial(self, experiment, participant):
            return ModularPage(
                "color_blindness_trial",
                ImagePrompt(
                    self.stimulus.assets["image"].url,
                    "Write down the number in the image.",
                    width="350px",
                    height="344px",
                    hide_after=self.trial_maker.hide_after,
                    margin_bottom="15px",
                    text_align="center",
                ),
                TextControl(width="100px"),
                bot_response=lambda: self.definition["correct_answer"],
            )

    trial_class = ColorBlindnessTrial

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == trial.definition["correct_answer"]:
                score += 1
        passed = score >= self.performance_threshold
        return {"score": score, "passed": passed}


class ColorVocabularyTest(StaticTrialMaker):
    """
    The color vocabulary test checks the participant's ability to name colors. In each trial, a
    colored box is presented and the participant must choose from a set of colors which color is
    displayed in the box. The colors which are presented can be freely chosen by providing an
    optional ``colors`` parameter. See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color vocabulary test, default: "color_vocabulary_test".

    performance_threshold : int, optional
        The performance threshold, default: 4.

    colors : list, optional
        A list of tuples each representing one color option. The tuples are of
        the form ("color-name", [H, S, L]) corresponding to hue, saturation, and lightness.
        Hue takes integer values in [0-360]; saturation and lightness take integer values in [0-100].
        Default: the list of the six colors "turquoise", "magenta", "granite", "ivory", "maroon", and "navy".
    """

    def __init__(
        self,
        label="color_vocabulary_test",
        performance_threshold: int = 4,
        colors: list = None,
    ):
        if colors:
            self.colors = colors
        self.introduction = self.instruction_page()
        self.performance_threshold = performance_threshold

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(colors),
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

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

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == trial.definition["correct_answer"]:
                score += 1
        passed = score >= self.performance_threshold
        return {"score": score, "passed": passed}

    def get_stimulus_set(self, colors: list):
        stimuli = []
        words = [x[0] for x in colors]
        for (correct_answer, hsl) in colors:
            choices = words.copy()
            # Todo - think carefully about whether it's a good idea to have random
            # functions inside get_stimulus_set
            random.shuffle(choices)
            definition = {
                "target_hsl": hsl,
                "choices": choices,
                "correct_answer": correct_answer,
            }
            stimuli.append(Stimulus(definition=definition))
        return stimuli

    class ColorVocabularyTrial(StaticTrial):
        def show_trial(self, experiment, participant):
            return ModularPage(
                "color_vocabulary_trial",
                ColorPrompt(
                    self.definition["target_hsl"],
                    "Which color is shown in the box?",
                    text_align="center",
                ),
                PushButtonControl(
                    self.definition["choices"],
                    arrange_vertically=False,
                    style="min-width: 150px; margin: 10px",
                ),
                bot_response=lambda: self.definition["correct_answer"],
            )

    trial_class = ColorVocabularyTrial


class HeadphoneTest(StaticTrialMaker):
    """
    The headphone test makes sure that the participant is wearing headphones. In each trial,
    three sounds separated by silences are played and the participent's must judge which sound
    was the softest (quietest). See the documentation for further details.

    Parameters
    ----------

    label : string, optional
        The label for the color headphone check, default: "headphone_test".

    media_url : string, optional
        The url under which the images to be displayed can be referenced, default:
        "https://s3.amazonaws.com/headphone-check"

    time_estimate_per_trial : float, optional
        The time estimate in seconds per trial, default: 7.5.

    performance_threshold : int, optional
        The performance threshold, default: 4.
    """

    def __init__(
        self,
        label="headphone_test",
        media_url: str = "https://s3.amazonaws.com/headphone-check",
        time_estimate_per_trial: float = 7.5,
        performance_threshold: int = 4,
    ):
        self.introduction = self.instruction_page()
        self.time_estimate_per_trial = time_estimate_per_trial
        self.performance_threshold = performance_threshold

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(media_url),
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

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

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == trial.definition["correct_answer"]:
                score += 1
        passed = score >= self.performance_threshold
        return {"score": score, "passed": passed}

    class HeadphoneTrial(StaticTrial):
        def show_trial(self, experiment, participant):
            return ModularPage(
                "headphone_trial",
                AudioPrompt(
                    self.assets["stimulus"],
                    "Which sound was softest (quietest) -- 1, 2, or 3?",
                ),
                PushButtonControl(["1", "2", "3"]),
                events={
                    "responseEnable": Event(is_triggered_by="promptEnd"),
                    "submitEnable": Event(is_triggered_by="promptEnd"),
                },
                bot_response=lambda: self.definition["correct_answer"],
            )

    trial_class = HeadphoneTrial

    def get_stimulus_set(self, media_url: str):
        return [
            Stimulus(
                definition={
                    "label": label,
                    "correct_answer": answer,
                    "url": f"{media_url}/antiphase_HC_{label}.wav",  # Redundant but kept for back-compatibility
                },
                assets={
                    "stimulus": ExternalAsset(
                        f"headphone_test_{label}",
                        url=f"{media_url}/antiphase_HC_{label}.wav",
                    )
                },
            )
            for label, answer in [
                ("ISO", "2"),
                ("IOS", "3"),
                ("SOI", "1"),
                ("SIO", "1"),
                ("OSI", "2"),
                ("OIS", "3"),
            ]
        ]


class AudioForcedChoiceTest(StaticTrialMaker):
    """
    The audio forced choice test makes sure that the participant can correctly classify a sound.
    In each trial, the participant hears one sound and has to pick one answer from a list.
    Some use-cases where this test can be of use:
    - You only have a few stimuli with ground truth annotation and want the participant to annotate the rest. You can
      use the test to make sure that the participant is capable to classify the stimuli correctly.
    - You implemented an experiment that assumes participants are able to classify sounds (e.g., which bird sings the
      played bird song)
    - During the main experiment, participants record themselves reading a sentence. There can be issues with the
      recording e.g., the participant misreads the sentence. Familiarizing the participants with these kind of errors
      beforehand can raise awareness of these issues. Furthermore, participants can be under the impression that their
      own recordings are being rated by others, which might increase motivation to do the task properly.


    Parameters
    ----------

    csv_path :
        The path to a valid csv file with headers. The file must contain the two columns `url` and `answer`.

    answer_options :
        List of answer options.

    instructions :
        Text of initial instruction page.

    question :
        Question asked at every trial of the test. If the table already contains a column `question` this value will be
        taken.

    performance_threshold :
        The performance threshold. The amount of mistakes the participant is allowed to make before failing the
        performance check.

    label :
        The label for the audio forced choice check, default: "audio_forced_choice_test".

    time_estimate_per_trial :
        The time estimate in seconds per trial, default: 8.

    n_stimuli_to_use :
        If None, all stimuli are used (default). If integer is supplied, n random stimuli are taken.

    specific_stimuli :
        If None, all stimuli are used (default). If list of indexes is supplied, only indexes are used.

    """

    def __init__(
        self,
        csv_path: str,
        answer_options: list,
        instructions: str,
        question: str,
        performance_threshold: int,
        label="audio_forced_choice_test",
        time_estimate_per_trial: float = 8.0,
        n_stimuli_to_use: Optional[int] = None,
        specific_stimuli: Optional[List] = None,
    ):
        assert not (specific_stimuli is not None and n_stimuli_to_use is not None)

        self.answer_options = answer_options
        stimuli = self.load_stimuli(csv_path, question)

        self.instructions = instructions

        self.n_stimuli_to_use = n_stimuli_to_use

        self.check_stimuli(stimuli, specific_stimuli)

        self.time_estimate_per_trial = time_estimate_per_trial
        self.introduction = self.instruction_page()
        self.performance_threshold = performance_threshold

        super().__init__(
            id_=label,
            trial_class=self.trial_class,
            phase="screening",
            stimuli=self.get_stimulus_set(label, stimuli, specific_stimuli),
            check_performance_at_end=True,
            fail_trials_on_premature_exit=False,
        )

    def load_stimuli(self, csv_path, question):
        assert file_exists(csv_path)

        df = pd.read_csv(csv_path)
        columns = list(df.columns)

        assert "url" in columns
        assert "answer" in columns

        stimuli = []
        for index, row in df.iterrows():
            stimulus = dict(row)
            assert stimulus["url"].startswith("http")  # Make sure url starts with http
            stimulus["answer_options"] = self.answer_options
            if "question" not in columns:
                stimulus["question"] = question
            stimuli.append(stimulus)
        return stimuli

    def check_stimuli(self, stimuli, specific_stimuli):
        used_answer_options = list(set([s["answer"] for s in stimuli]))

        # Make sure that all answer options in the file are also selectable during the experiment
        assert all([answer in self.answer_options for answer in used_answer_options])

        if specific_stimuli is not None:
            # Make sure all indexes are valid (i.e., are integers, go from 0 to max id)
            assert all([isinstance(i, int) for i in specific_stimuli])
            assert min(specific_stimuli) >= 0
            assert max(specific_stimuli) < len(stimuli)

        if self.n_stimuli_to_use is not None:
            assert self.n_stimuli_to_use <= len(
                stimuli
            )  # Cannot select more stimuli than which are available
            assert self.n_stimuli_to_use > 0  # Must be an integer larger than 0

    def instruction_page(self):
        return InfoPage(
            Markup(self.instructions),
            time_estimate=10,
        )

    class AudioForcedChoiceTrial(StaticTrial):
        def show_trial(self, experiment, participant):
            return ModularPage(
                "audio_forced_choice_trial",
                AudioPrompt(
                    self.stimulus.assets["stimulus"],
                    self.definition["question"],
                ),
                PushButtonControl(self.definition["answer_options"]),
                bot_response=lambda: self.definition["answer"],
            )

    trial_class = AudioForcedChoiceTrial

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        score = 0
        for trial in participant_trials:
            if trial.answer == trial.definition["answer"]:
                score += 1
        passed = score >= self.performance_threshold
        return {"score": score, "passed": passed}

    def get_stimulus_set(self, label, stimuli, specific_stimuli):
        if self.n_stimuli_to_use is not None:
            shuffle(stimuli)
            stimuli = stimuli[: self.n_stimuli_to_use]

        elif specific_stimuli is not None:
            stimuli = [stimuli[i] for i in specific_stimuli]

        return [
            Stimulus(
                definition=stimulus,
                assets={
                    "stimulus": ExternalAsset(
                        f"{label}_{i}",
                        stimulus["url"],
                    )
                },
            )
            for i, stimulus in enumerate(stimuli)
        ]
