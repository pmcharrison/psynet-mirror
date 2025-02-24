import numpy as np
from markupsafe import Markup
from dominate import tags

from psynet.page import InfoPage, ModularPage, wait_while
from psynet.modular_page import PushButtonControl, AudioPrompt, RadioButtonControl, AudioMeterControl, \
    AudioRecordControl
from psynet.trial.audio import AudioRecordTrial
from psynet.timeline import CodeBlock, PageMaker, join, Event, Module, ProgressStage, ProgressDisplay
from psynet.js_synth import JSSynth, Note, Rest, HarmonicTimbre
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.trial import compile_nodes_from_directory

# singing
from sing4me import singing_extract as sing
from . sing import melodies
from . sing.params import singing_2intervals


roving_width = 2.5
roving_mean = dict(
    default=55,
    low=49,
    high=61
)


# volume test for tone js
def tonejs_volume_test(timbre, note_duration, note_silence, time_estimate_per_trial=5):
    return ModularPage(
        "tone_js_volume_test",
        JSSynth(
            Markup(
                """
                        <h3>Volume calibration</h3>
                        <hr>
                        Set the volume in your laptop to a level in which you can hear each note properly.
                        <hr>
                        """
            ),
            sequence=[
                Note(x)
                for x in melodies.convert_interval_sequence_to_absolute_pitches(
                    intervals=melodies.sample_interval_sequence(
                        n_int=11,
                        max_interval_size=8.5,
                        max_melody_pitch_range=99,
                        discrete=False,
                        reference_mode="first_note",
                    ),
                    reference_pitch=melodies.sample_reference_pitch(55, 2.5),
                    reference_mode="first_note",
                )
            ],
            timbre=timbre,
            default_duration=note_duration,
            default_silence=note_silence,
        ),
        time_estimate=time_estimate_per_trial,
        events={
            "restartMelody": Event(
                is_triggered_by="promptEnd",
                delay=1.0,
                js="psynet.trial.restart()"
            ),
            "submitEnable": Event(is_triggered_by="trialStart", delay=5)
        }
    )


# self-report questions for input and output
def audio_output_question():
    return ModularPage(
        "audio_output",
        prompt="What are you using to play sound?",
        control=RadioButtonControl(
            choices=["headphones", "earphones", "internal_speakers", "external_speakers"],
            labels=[
                "Headphones",
                "Earphones",
                "Internal computer speakers",
                "External computer speakers",
            ],
            show_free_text_option=True,
        ),
        time_estimate=7.5,
        save_answer="audio_output"
    )


def audio_input_question():
    return ModularPage(
        "audio_input",
        prompt="What are you using to record sound?",
        control=RadioButtonControl(
            choices=["headphones", "earphones", "internal_microphone", "external_microphone"],
            labels=[
                "Headphone microphone",
                "Earphone microphone",
                "A microphone inside your computer",
                "An external microphone attached to your computer",
            ],
            show_free_text_option=True,
        ),
        time_estimate=7.5,
        save_answer="audio_input"
    )


# microphone test (optimized for singing)
class SingingTestControl(AudioMeterControl):
    # adjust default parameters to work nicely with voice
    decay = {"display": 0.1, "high": 0.1, "low": 0.1}
    threshold = {"high": -3, "low": -25}  #
    grace = {"high": 0.2, "low": 1.5}
    warn_on_clip = False
    msg_duration = {"high": 0.25, "low": 0.25}


def mic_test():
    html = tags.div()

    with html:
        tags.p(
            "Please try singing into the microphone. If your microphone is set up correctly, "
            "you should see the audio meter move. If it is not working, please update your audio settings and "
            "try again."
        )

        with tags.div():
            tags.attr(cls="alert alert-primary")
            tags.p(tags.ul(
                tags.li("If you see a dialog box requesting microphone permissions, please click 'Accept'."),
                tags.li("You can refresh the page if you like."),
            ))

    return ModularPage(
        "mic_test",
        html,
        SingingTestControl(),
        events={"submitEnable": Event(is_triggered_by="trialStart", delay=5)},
        time_estimate=10,
    )


# singing familiarization
def recording_example():
    return join(
        InfoPage(
            Markup(
                f"""
                <h3>Recording Example</h3>
                <hr>
                First, we will test if you can record your voice with the computer microphone. 
                <br><br>
                When ready, go to the next page and <b><b>sing 2 notes</b></b> using the syllable 'TA'.<br>
                (separate each note with a silence). 
                <hr>
                """
            ),
            time_estimate=5,
        ),
        ModularPage(
            "singing_record_example",
            Markup(
                f"""
                <h3>Recording Example</h3>
                Sing 2 notes to the syllable 'TA'<br> 
                <i>Leave a silent gap between the notes</i>
                """
            ),
            AudioRecordControl(
                duration=5.0,
                show_meter=True,
                controls=False,
                auto_advance=False,
            ),
            time_estimate=5,
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(5, "Recording.. Sing 2 notes!", "red"),
                ],
            ),
        ),
        wait_while(
            lambda participant: not participant.assets["singing_record_example"].deposited,
            expected_wait=5.0,
            log_message="Waiting for the recording to finish uploading",
        ),
        PageMaker(
            lambda participant: ModularPage(
                "playback",
                AudioPrompt(
                    participant.assets["singing_record_example"],
                    Markup(
                        """
                        <h3>Can you hear your recording?</h3>
                        <hr>
                        If you do not hear your recording, please make sure
                        to use a working microphone so we can record your voice and continue with the experiment. 
                        <hr>
                        """
                    ),
                ),
            ),
            time_estimate=5,
        ),
    )


########################################################################################################################
# Singing performance test: singing_feedback and singing_test
########################################################################################################################
# global variables singing performance test
performance_trial_time_estimate = 8
duration_melody = 2.5
duration_recording = 3.5
save_plot_prescreen = True

# tests
num_trials_test = 10
num_trials_feedback = 2
performance_threshold = 5  # this determines when we fail people in the main performance test

roving_mean_low = 49
roving_mean_high = 61

# timbre
note_duration_tonejs = 0.8
note_silence_tonejs = 0
TIMBRE = dict(
    default=HarmonicTimbre(
        attack=0.01,  # Attack phase duration in seconds
        decay=0.05,  # Decay phase duration in seconds
        sustain_amp=0.6,  # Amplitude fraction to decay to relative to max amplitude --> 0.4, 0.7
        release=0.55,  # Release phase duration in seconds
        num_harmonics=10,  # Acd ctual number of partial harmonics to use
        roll_off=14,  # Roll-off in units of dB/octave,
    )
)

nodes_singing_performance_test = [
    StaticNode(
        definition={
            "interval": interval,
            "target_pitches": melodies.convert_interval_sequence_to_absolute_pitches(
                intervals=[interval],
                reference_pitch=melodies.sample_reference_pitch(
                    roving_mean[register],
                    roving_width
                ),
                reference_mode="previous_note",
            ),
        },
    )
    for interval in [-1.3, -2.6, 0.0, 1.3, 2.6]
    for register in ["low", "high"]
]


nodes_singing_performance_feedback = [
    StaticNode(
        definition={
            "interval": interval,
            "target_pitches": melodies.convert_interval_sequence_to_absolute_pitches(
                intervals=[interval],
                reference_pitch=melodies.sample_reference_pitch(
                    roving_mean[register],
                    roving_width
                ),
                reference_mode="previous_note",
            ),
        },
    )
    for interval in [-1.3, -2.6, 1.3, 2.6]
    for register in ["low", "high"]
]


class SingingPerformanceTestTrial(AudioRecordTrial, StaticTrial):
    time_estimate = performance_trial_time_estimate

    def show_trial(self, experiment, participant):
        # count trials
        current_trial = self.position + 1
        total_num_trials = num_trials_test
        show_current_trial = f'<br><br>Trial number {current_trial} out of {total_num_trials} trials.'

        return ModularPage(
            "singing_performance_test_trial",
            JSSynth(
                Markup(
                    f"""
                    <h3>Imitate the melody</h3>
                    This melody has two notes: <b><b>Sing each note back to the syllable 'TA'.</b></b><br>
                    <i>leave a silent gap between the notes</i>
                    <br><br>
                    {show_current_trial}
                    """
                ),
                [Note(pitch) for pitch in self.definition["target_pitches"]],
                timbre=TIMBRE,
                default_duration=note_duration_tonejs,
                default_silence=note_silence_tonejs,
            ),
            control=AudioRecordControl(
                duration=duration_recording,
                show_meter=False,
                controls=False,
                auto_advance=False,
                bot_response_media="example_audio.wav",
            ),
            events={
                "promptStart": Event(is_triggered_by="trialStart"),
                "recordStart": Event(is_triggered_by="promptEnd", delay=0.25),
            },
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(duration_melody, "Listen to the melody...", "orange"),
                    ProgressStage(duration_recording, "Recording...SING THE MELODY!", "red"),
                    ProgressStage(0.5, "Done!", "green", persistent=True),
                ],
            ),
            time_estimate=performance_trial_time_estimate,
        )

    def analyze_recording(self, audio_file: str, output_plot: str):
        raw = sing.analyze(
            audio_file,
            singing_2intervals,
            target_pitches=self.definition["target_pitches"],
            plot_options=sing.PlotOptions(
                save=save_plot_prescreen, path=output_plot, format="png"
            ),
        )
        raw = [
            {key: melodies.as_native_type(value) for key, value in x.items()} for x in raw
        ]
        sung_pitches = [x["median_f0"] for x in raw]
        sung_intervals = melodies.convert_absolute_pitches_to_interval_sequence(
            sung_pitches,
            "previous_note"
        )
        target_intervals = melodies.convert_absolute_pitches_to_interval_sequence(
            self.definition["target_pitches"],
            "first_note"
        )
        stats = sing.compute_stats(
            sung_pitches,
            self.definition["target_pitches"],
            sung_intervals,
            target_intervals
        )

        # failing criteria
        correct_num_notes = stats["num_sung_pitches"] == stats["num_target_pitches"]
        max_interval_error_ok = stats["max_abs_interval_error"] < 3
        direction_accuracy_ok = stats["direction_accuracy"] == 100

        failed_options = [
            correct_num_notes,
            max_interval_error_ok,
            direction_accuracy_ok
        ]
        reasons = [
            "Wrong number of sung notes",
            "max interval error is larger than 3",
            "direction accuyracy is wrong"
        ]
        if False in failed_options:
            failed = True
            index = failed_options.index(False)
            reason = reasons[index]
        else:
            failed = False
            reason = "All good"

        return {
            "failed": failed,
            "reason": reason,
            "target_pitches": self.definition["target_pitches"],
            "target_intervals": target_intervals,
            "sung_pitches": sung_pitches,
            "sung_intervals": sung_intervals,
            "raw": raw,
            # "stats": stats,
            "mean_pitch_diffs": stats["mean_pitch_diffs"],
            "max_abs_pitch_error": stats["max_abs_pitch_error"],
            "mean_interval_diff": stats["mean_interval_diff"],
            "max_abs_interval_error": stats["max_abs_interval_error"],
            "direction_accuracy": stats["direction_accuracy"],
        }


class SingingPerformanceFeedbackTrial(AudioRecordTrial, StaticTrial):
    time_estimate = performance_trial_time_estimate
    wait_for_feedback = True

    def show_trial(self, experiment, participant):
        # count trials
        current_trial = self.position + 1
        total_num_trials = num_trials_feedback
        show_current_trial = f'<br><br>Trial number {current_trial} out of {total_num_trials} trials.'

        return ModularPage(
            "singing_performance_feedback_trial",
            JSSynth(
                Markup(
                    f"""
                    <h3>Imitate the melody</h3>
                    This melody has two notes: <b><b>Sing each note back to the syllable 'TA'.</b></b><br>
                    <i>leave a silent gap between the notes</i>
                    <br><br>
                    {show_current_trial}
                    """
                ),
                [Note(pitch) for pitch in self.definition["target_pitches"]],
                timbre=TIMBRE,
                default_duration=note_duration_tonejs,
                default_silence=note_silence_tonejs,
            ),
            control=AudioRecordControl(
                duration=duration_recording,
                show_meter=False,
                controls=False,
                auto_advance=False,
                bot_response_media="example_audio.wav",
            ),
            events={
                "promptStart": Event(is_triggered_by="trialStart"),
                "recordStart": Event(is_triggered_by="promptEnd", delay=0.25),
            },
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(duration_melody, "Listen to the melody...", "orange"),
                    ProgressStage(duration_recording, "Recording...SING THE MELODY!", "red"),
                    ProgressStage(0.5, "Done!", "green", persistent=True),
                ],
            ),
            time_estimate=performance_trial_time_estimate,
        )

    def gives_feedback(self, experiment, participant):
        return True

    def show_feedback(self, experiment, participant):
        output_analysis = self.analysis
        num_sung_pitches = output_analysis["num_sung_pitches"]

        if num_sung_pitches == 2:
            return InfoPage(
                Markup(
                    f"""
                    <h3>Your performance is great!</h3>
                    <hr>
                    We detected {num_sung_pitches} notes in your recording.
                    <hr>
                    """
                ),
                time_estimate=5
            )
        if num_sung_pitches == 0:
            return InfoPage(
                Markup(
                    f"""
                   <h3>Your performance is bad...</h3>
                   <hr>
                   We could not detect any note in your recording.<br><br> 
                    Please following the instructions:
                    <ol><li>Sing each note clearly using the syllable 'TA'.</li>
                        <li>Make sure you computer microphone is working and you are in a quiet environment.</li>
                        <li>Leave a silent gap between the notes.</li>
                        <li>Sing each note for about 1 second.</li>
                    </ol>
                    <b><b>If you do not improve your performance, the experiment will terminate early</b></b> 
                    <hr>
                    """
                ),
                time_estimate=5
            )
        else:
            return InfoPage(
                Markup(
                    f"""
                    <h3>You can do better...</h3>
                    <hr>
                    We detected {num_sung_pitches} notes in your recording, but we asked
                    you to <b><b>sing 2 notes</b></b>.<br><br> 
                    Please following the instructions:
                    <ol><li>Sing each note clearly using the syllable 'TA'.</li>
                        <li>Make sure you computer microphone is working and you are in a quiet environment.</li>
                        <li>Leave a silent gap between the notes.</li>
                        <li>Sing each note for about 1 second.</li>
                    </ol>
                    <b><b>If you do not improve your performance, the experiment will terminate early</b></b> 
                    <hr>
                    """
                ),
                time_estimate=5
            )

    def analyze_recording(self, audio_file: str, output_plot: str):
        raw = sing.analyze(
            audio_file,
            singing_2intervals,
            target_pitches=self.definition["target_pitches"],
            plot_options=sing.PlotOptions(
                save=save_plot_prescreen, path=output_plot, format="png"
            ),
        )
        raw = [
            {key: melodies.as_native_type(value) for key, value in x.items()} for x in raw
        ]
        sung_pitches = [x["median_f0"] for x in raw]

        if len(sung_pitches) == 2:
            correct_num_notes = True
            failed = False
        else:
            correct_num_notes = False
            failed = True

        return {
            "failed": failed,
            "correct_num_notes": correct_num_notes,
            "num_sung_pitches": len(sung_pitches),
        }


class SingingPerformanceFeedbackTrialMaker(StaticTrialMaker):
    performance_check_type = "performance"
    give_end_feedback_passed = True
    end_performance_check_waits = True

    def performance_check(self, experiment, participant, participant_trials):
        score = 0

        for trial in participant_trials:
            if not trial.analysis["failed"]:
                score += 1
        passed = score >= 0.5

        return {"score": score, "passed": passed}

    def get_end_feedback_passed_page(self, score):
        score_to_display = "NA" if score is None else f"{((score / num_trials_feedback) * 100):.0f}"

        return InfoPage(
            Markup(f"""Your performance score was <strong>{score_to_display}&#37;</strong>."""),
            time_estimate=3,
        )


class SingingPerformanceTestTrialMaker(StaticTrialMaker):
    performance_check_type = "performance"
    give_end_feedback_passed = True
    end_performance_check_waits = True

    def performance_check(self, experiment, participant, participant_trials):
        score = 0
        list_max_abs_interval_error = []
        list_direction_accuracy = []
        list_sung_pitches = []

        for trial in participant_trials:
            # list_max_abs_pitch_diff.append(trial.analysis["max_abs_pitch_error"])
            list_max_abs_interval_error.append(trial.analysis["max_abs_interval_error"])
            list_direction_accuracy.append(trial.analysis["direction_accuracy"])
            list_sung_pitches.append(trial.analysis["sung_pitches"])
            if not trial.analysis["failed"]:
                score += 1
        passed = score >= performance_threshold

        # store variables in particaipnt table
        participant.var.set("singing_performance", score)
        participant.var.set("list_max_abs_interval_error", list_max_abs_interval_error)
        participant.var.set("list_direction_accuracy", list_direction_accuracy)

        # determine register
        flat_list_sung_pitches = [x for xs in list_sung_pitches for x in xs]
        median_pitch = np.median(flat_list_sung_pitches)
        distance_to_low_register = abs(median_pitch - roving_mean_low)
        distance_to_high_register = abs(median_pitch - roving_mean_high)

        if distance_to_low_register < distance_to_high_register:
            predicted_register = "low"
        elif distance_to_low_register > distance_to_high_register:
            predicted_register = "high"
        else:
            predicted_register = "undefined"

        participant.var.set("sung_median_pitch", median_pitch)
        participant.var.set("distance_to_low_register", distance_to_low_register)
        participant.var.set("distance_to_high_register", distance_to_high_register)
        participant.var.set("predicted_register", predicted_register)

        return {"score": score, "passed": passed}

    def get_end_feedback_passed_page(self, score):
        score_to_display = "NA" if score is None else f"{((score / num_trials_test) * 100):.0f}"

        return InfoPage(
            Markup(
                f"""
                <h4>Congratulations, you passed the singing test.</h4>
                Your performance score was <strong>{score_to_display}&#37;</strong>.
                """
            ),
            time_estimate=3,
        )


def singing_performance():
    return join(
        InfoPage(
            Markup(
                f"""
                <h3>Singing Practice</h3>
                <hr>
                <b><b>You will hear a melody with 2 notes and your goal is to sing each note back as 
                accurately as possible.</b></b><br>
                <i>Note:</i> Use the syllable 'TA' to sing each note and leave a silent gap between notes. <br><br>
                We will provide feedback after each trial.
                <hr>
                When ready, click <b><b>next</b></b> to start singing.
                """
            ),
            time_estimate=5,
        ),
        SingingPerformanceFeedbackTrialMaker(
            id_="singing_performance_feedback",
            trial_class=SingingPerformanceFeedbackTrial,
            nodes=nodes_singing_performance_feedback,
            expected_trials_per_participant=num_trials_feedback,
            max_trials_per_participant=num_trials_feedback,
            recruit_mode="n_trials",
            target_n_participants=None,
            check_performance_every_trial=False,
            check_performance_at_end=True,
        ),
        InfoPage(
            Markup(
                f"""
                <h3>Singing Test</h3>
                <hr>
                We will now test your singing performance in a total of {num_trials_test} trials.<br>
                Like before, your goal is to listen to each melody and sing it back to the syllable 'TA'.
                <br><br>
                <b><b>If you do not pass the test, the experiment will terminate.</b></b> 
                <hr>
                When ready, click <b><b>next</b></b> to start singing.
                """
            ),
            time_estimate=5,
        ),
        SingingPerformanceTestTrialMaker(
            id_="singing_performance_test",
            trial_class=SingingPerformanceTestTrial,
            nodes=nodes_singing_performance_test,
            expected_trials_per_participant=num_trials_test,
            max_trials_per_participant=num_trials_test,
            recruit_mode="n_trials",
            target_n_participants=None,
            check_performance_every_trial=False,
            check_performance_at_end=True,
        ),
    )
