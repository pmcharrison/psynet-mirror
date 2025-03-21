# This file contains the code with pre-screeners for singing experiments. 
# This code is based on the study by Anglada-Tort et al. (2023).
# Please see the methods section in the study for more details. 
# Anglada-Tort, M., Harrison, P. M., Lee, H., & Jacoby, N. (2023). Large-scale iterated 
# singing experiments reveal oral transmission mechanisms underlying music evolution. 
# Current Biology, 33(8), 1472-1486.

# Import necessary libraries and modules
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

# Import custom modules for singing analysis and melodies
from sing4me import singing_extract as sing
from . sing import melodies
from . sing.params import singing_2intervals

# Define global variables for roving pitch range
roving_width = 2.5
roving_mean = dict(
    default=55,  # Default pitch reference
    low=49,      # Low pitch reference
    high=61      # High pitch reference
)

# Function to test volume levels using Tone.js
def tonejs_volume_test(timbre, note_duration, note_silence, time_estimate_per_trial=5):
    """
    This function creates a page for volume calibration using Tone.js.
    Participants adjust their device volume to hear notes properly.
    """
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
                        n_int=11,  # Number of intervals in the melody
                        max_interval_size=8.5,  # Maximum interval size
                        max_melody_pitch_range=99,  # Maximum pitch range
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
                js="psynet.trial.restart()"  # Restart melody playback
            ),
            "submitEnable": Event(is_triggered_by="trialStart", delay=5)  # Enable submit button after 5 seconds
        }
    )

# Function to ask participants about their audio output device
def audio_output_question():
    """
    This function creates a page to ask participants about their audio output device.
    """
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
            show_free_text_option=True,  # Allow participants to specify other options
        ),
        time_estimate=7.5,
        save_answer="audio_output"  # Save the participant's response
    )

# Function to ask participants about their audio input device
def audio_input_question():
    """
    This function creates a page to ask participants about their audio input device.
    """
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
            show_free_text_option=True,  # Allow participants to specify other options
        ),
        time_estimate=7.5,
        save_answer="audio_input"  # Save the participant's response
    )

# Custom AudioMeterControl class optimized for singing
class SingingTestControl(AudioMeterControl):
    """
    This class customizes the audio meter control for singing tests.
    It adjusts parameters like decay, threshold, and grace period to work well with voice input.
    """
    decay = {"display": 0.1, "high": 0.1, "low": 0.1}
    threshold = {"high": -3, "low": -25}  # Threshold levels for high and low audio signals
    grace = {"high": 0.2, "low": 1.5}  # Grace period for high and low signals
    warn_on_clip = False  # Disable warnings for audio clipping
    msg_duration = {"high": 0.25, "low": 0.25}  # Duration of messages for high and low signals

# Function to test microphone functionality
def mic_test():
    """
    This function creates a page to test if the participant's microphone is working.
    Participants are asked to sing into the microphone and check if the audio meter moves.
    """
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
        events={"submitEnable": Event(is_triggered_by="trialStart", delay=5)},  # Enable submit button after 5 seconds
        time_estimate=10,
    )

# Function to familiarize participants with the recording process
def recording_example():
    """
    This function guides participants through a recording example.
    Participants are asked to sing 2 notes using the syllable 'TA' and check if their recording is audible.
    """
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
                duration=5.0,  # Duration of the recording
                show_meter=True,  # Show audio meter during recording
                controls=False,  # Disable playback controls
                auto_advance=False,  # Do not auto-advance to the next page
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

# Global variables for the singing performance test
performance_trial_time_estimate = 8  # Estimated time per trial
duration_melody = 2.5  # Duration of the melody playback in seconds
duration_recording = 3.5  # Duration of the recording in seconds
save_plot_prescreen = True  # Whether to save plots during pre-screening

# Test parameters
num_trials_test = 10  # Number of trials in the main singing test
num_trials_feedback = 2  # Number of feedback trials during practice
performance_threshold = 5  # Minimum score required to pass the main performance test

# Roving pitch range for low and high registers
roving_mean_low = 49
roving_mean_high = 61

# Timbre settings for the synthesized notes
note_duration_tonejs = 0.8  # Duration of each note in seconds
note_silence_tonejs = 0  # Silence between notes in seconds
TIMBRE = dict(
    default=HarmonicTimbre(
        attack=0.01,  # Attack phase duration in seconds
        decay=0.05,  # Decay phase duration in seconds
        sustain_amp=0.6,  # Amplitude fraction to decay to relative to max amplitude
        release=0.55,  # Release phase duration in seconds
        num_harmonics=10,  # Number of partial harmonics to use
        roll_off=14,  # Roll-off in units of dB/octave
    )
)

# Define nodes for the singing performance test
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
    for interval in [-1.3, -2.6, 0.0, 1.3, 2.6]  # Intervals to test
    for register in ["low", "high"]  # Test both low and high registers
]

# Define nodes for the singing performance feedback trials
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
    for interval in [-1.3, -2.6, 1.3, 2.6]  # Intervals to test
    for register in ["low", "high"]  # Test both low and high registers
]

# Trial class for the main singing performance test
class SingingPerformanceTestTrial(AudioRecordTrial, StaticTrial):
    """
    A trial for the main singing performance test. Participants listen to a melody and sing it back.
    """
    time_estimate = performance_trial_time_estimate

    def show_trial(self, experiment, participant):
        """
        Display the trial page with instructions and melody playback.
        """
        current_trial = self.position + 1
        total_num_trials = num_trials_test
        show_current_trial = f'<br><br>Trial number {current_trial} out of {total_num_trials} trials.'

        return ModularPage(
            "singing_performance_test_trial",
            JSSynth(
                Markup(
                    f"""
                    <h3>Imitate the melody</h3>
                    This melody has two notes: <b>Sing each note back to the syllable 'TA'.</b><br>
                    <i>Leave a silent gap between the notes.</i>
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
        """
        Analyze the participant's recording and compute performance metrics.
        """
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

        # Failing criteria
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
            "Max interval error is larger than 3",
            "Direction accuracy is wrong"
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
            "mean_pitch_diffs": stats["mean_pitch_diffs"],
            "max_abs_pitch_error": stats["max_abs_pitch_error"],
            "mean_interval_diff": stats["mean_interval_diff"],
            "max_abs_interval_error": stats["max_abs_interval_error"],
            "direction_accuracy": stats["direction_accuracy"],
        }

def singing_performance():
    """
    Define the full singing performance test, including practice and main test phases.
    """
    return join(
        InfoPage(
            Markup(
                f"""
                <h3>Singing Practice</h3>
                <hr>
                <b>You will hear a melody with 2 notes and your goal is to sing each note back as 
                accurately as possible.</b><br>
                <i>Note:</i> Use the syllable 'TA' to sing each note and leave a silent gap between notes.<br><br>
                We will provide feedback after each trial.
                <hr>
                When ready, click <b>next</b> to start singing.
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
                <b>If you do not pass the test, the experiment will terminate.</b>
                <hr>
                When ready, click <b>next</b> to start singing.
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
