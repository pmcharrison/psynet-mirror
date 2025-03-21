# This is a singing demo showing how to create a singing imitation experiment using psynet.
# In this experiment, participants are asked to listen to a melody and sing it back as accurately as possible.
# The experiment includes a series of singing prescreens to ensure we can record the participant's voice.
# The experiment is based on the study by Anglada-Tort et al. (2023):
# Anglada-Tort, M., Harrison, P. M., Lee, H., & Jacoby, N. (2023). Large-scale iterated 
# singing experiments reveal oral transmission mechanisms underlying music evolution. 
# Current Biology, 33(8), 1472-1486.

from markupsafe import Markup
import random

import psynet.experiment
from psynet.asset import LocalStorage, DebugStorage
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, AudioRecordControl
from psynet.js_synth import JSSynth, Note, HarmonicTimbre

from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline, CodeBlock, conditional, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.trial.audio import AudioRecordTrial

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Importing prescreening tasks and singing-related modules
from .pre_screens import (
    tonejs_volume_test,
    mic_test,
    recording_example,
    singing_performance
)

from sing4me import singing_extract as sing
from .sing import melodies
from .sing.params import singing_2intervals


########################################################################################################################
# Global parameters
########################################################################################################################

# Decide whether you want to include singing prescreens (True) or not (False)
USE_SING_PRESCREENS = False  

# Experiment configuration
TIME_ESTIMATE_TRIAL = 10  # Estimated time per trial in seconds
NUM_PARTICIPANTS = 10  # Number of participants to recruit
NUM_MELODIES = 3  # Total number of melodies (stimuli/nodes)
TRIALS_PER_PARTICIPANT = NUM_MELODIES  # Number of trials per participant (same as number of melodies)

N_REPEAT_TRIALS = 0  # Number of repeated trials per participant
INITIAL_RECRUIT_SIZE = 20  # Initial recruitment size for participants
SAVE_PLOT = True  # Whether to save analysis plots

# Singing-related parameters
roving_width = 2.5  # Range for randomizing reference pitch
roving_mean = dict(
    default=55,  # Default reference pitch
    low=49,  # Low register reference pitch
    high=61  # High register reference pitch
)

NUM_NOTES = 5  # Number of notes in each melody
NUM_INT = NUM_NOTES - 1  # Number of intervals in each melody
SYLLABLE = "TA"  # Syllable to use while singing
TIME_AFTER_SINGING = 1  # Time after singing before the trial ends

# Melody constraints
REFERENCE_MODE = "pitch_mode"  # Mode for calculating intervals (e.g., pitch_mode, previous_note, first_note)
MAX_ABS_INT_ERROR_ALLOWED = 5.5  # Maximum allowed interval error (set to 999 if NUM_INT > 2)
MAX_INT_SIZE = 999  # Maximum interval size (deactivated)
MAX_MELODY_PITCH_RANGE = 999  # Maximum pitch range for melodies (deactivated)
MAX_INTERVAL2REFERENCE = 10  # Maximum interval size relative to the reference pitch
NUM_CHAINS_EXPERIMENT = 200  # Number of chains in the experiment (reduce if NUM_INT > 2)
NUM_TRIALS_PARTICIPANT = 40  # Number of trials per participant (reduce if NUM_INT > 2)

# Timbre configuration for synthesized melodies
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
pitch_duration = note_duration_tonejs + note_silence_tonejs


# Function to estimate the time required for each trial
def estimate_time_per_trial(pitch_duration, num_pitches, time_after_singing):
    melody_duration = pitch_duration * num_pitches  # Total duration of the melody
    singing_duration = melody_duration + time_after_singing  # Total duration including singing
    return melody_duration, singing_duration


melody_duration, singing_duration = estimate_time_per_trial(
    pitch_duration,
    (NUM_NOTES + 1),  # Number of notes in the melody plus one
    TIME_AFTER_SINGING
)


########################################################################################################################
# Stimuli
########################################################################################################################

# Function to generate random melodies based on constraints
def generate_random_melody(mel_id, roving_mean, roving_width, max_interval2reference, num_notes):
    # Sample a reference pitch
    reference_pitch = melodies.sample_reference_pitch(
        roving_mean,
        roving_width,
    )
    # Generate target pitches based on the reference pitch
    target_pitches = melodies.sample_absolute_pitches(
        reference_pitch=reference_pitch,
        max_interval2reference=max_interval2reference,
        num_pitches=num_notes
    )
    # Convert target pitches to intervals
    target_intervals = melodies.convert_absolute_pitches_to_interval_sequence(target_pitches, "previous_note")
    # Calculate intervals relative to the reference pitch
    target_intervals2reference = melodies.convert_absolute_pitches_to_intervals2reference(
        target_pitches, reference_pitch
    )
    return dict(
        melody_id="Melody_" + str(mel_id),
        reference_pitch=reference_pitch,
        target_pitches=target_pitches,
        target_intervals=target_intervals,
        target_intervals2reference=target_intervals2reference
    )

# Create nodes for each melody
nodes = [
    StaticNode(
        definition={
            "melody": generate_random_melody(i, roving_mean["high"], roving_width, MAX_INTERVAL2REFERENCE, NUM_NOTES)
        },
    )
    for i in range(1, (NUM_MELODIES + 1))
]


########################################################################################################################
# Experiment parts
########################################################################################################################

# Define a custom trial class for singing tasks
class SingingTrial(AudioRecordTrial, StaticTrial):
    time_estimate = TIME_ESTIMATE_TRIAL

    def show_trial(self, experiment, participant):
        melody = self.definition

        # Adjust melody register based on participant's assigned register
        if self.participant.var.register == "high":
            target_pitches = melody['melody']['target_pitches']
        else:
            target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]  # Lower the pitch by an octave

        current_trial = self.position + 1
        show_current_trial = f'<i>Trial number {current_trial} out of {(TRIALS_PER_PARTICIPANT + N_REPEAT_TRIALS)} trials.</i>'

        return ModularPage(
            "singing",
            JSSynth(
                Markup(
                    f"""
                <h3>Sing back the melody</h3>
                <hr>
                <b><b>This melody has {len(target_pitches)} notes</b></b>: Sing each note clearly using the syllable '{SYLLABLE}'.
                <br><i>Leave short gaps between notes.</i>
                <br><br>
                {show_current_trial}
                <hr>
                """
                ),
                [Note(pitch) for pitch in target_pitches],
                timbre=TIMBRE,
                default_duration=note_duration_tonejs,
                default_silence=note_silence_tonejs,
            ),
            control=AudioRecordControl(
                duration=singing_duration,
                show_meter=True,
                controls=False,
                auto_advance=False,
                bot_response_media="audio_5notes.wav",
            ),
            events={
                "promptStart": Event(is_triggered_by="trialStart"),
                "recordStart": Event(is_triggered_by="promptEnd", delay=0.25),
            },
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(melody_duration, "Listen to the melody...", "orange"),
                    ProgressStage(singing_duration, "Recording...SING THE MELODY!", "red"),
                    ProgressStage(0.5, "Done!", "green", persistent=True),
                ],
            ),
            time_estimate=TIME_ESTIMATE_TRIAL,
        )

    def analyze_recording(self, audio_file: str, output_plot: str):
        melody = self.definition

        # Adjust melody register based on participant's assigned register
        if self.participant.var.register == "high":
            target_pitches =  melody['melody']['target_pitches']
            reference_pitch =  melody['melody']['reference_pitch']
        else:
            target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]
            reference_pitch = melody['melody']['reference_pitch'] - 12

        # Analyze the participant's singing
        raw = sing.analyze(
            audio_file,
            singing_2intervals,
            target_pitches=target_pitches,
            plot_options=sing.PlotOptions(
                save=SAVE_PLOT, path=output_plot, format="png"
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
            target_pitches,
            "previous_note"
        )
        sung_intervals2reference = melodies.convert_absolute_pitches_to_intervals2reference(
            sung_pitches,
            reference_pitch
        )
        stats = sing.compute_stats(
            sung_pitches,
            target_pitches,
            sung_intervals,
            target_intervals
        )
        is_failed = melodies.failing_criteria(
            sung_intervals,
            sung_pitches,
            reference_pitch,
            NUM_INT,
            MAX_INT_SIZE,  # Only used in interval representation, currently deactivated
            MAX_MELODY_PITCH_RANGE,  # Only used in interval representation, currently deactivated
            REFERENCE_MODE,
            stats,
            MAX_ABS_INT_ERROR_ALLOWED,  # Deactivated
            (MAX_INTERVAL2REFERENCE * 2)  # Only used in pitch mode
        )

        failed = is_failed["failed"]
        reason = is_failed["reason"]

        # Convert back to high register if needed
        if self.participant.var.register == "low":
            target_pitches = [(i + 12) for i in target_pitches]
            sung_pitches = [(i + 12) for i in sung_pitches]
            reference_pitch = reference_pitch + 12

        return {
            "failed": failed,
            "reason": reason,
            "register": self.participant.var.register,
            "reference_pitch": reference_pitch,
            "target_pitches": target_pitches,
            "num_target_pitches": len(target_pitches),
            "target_intervals": target_intervals,
            "sung_pitches": sung_pitches,
            "num_sung_pitches": len(sung_pitches),
            "sung_intervals": sung_intervals,
            "sung_intervals2reference": sung_intervals2reference,
            "raw": raw,
            "save_plot": SAVE_PLOT,
            "stats": stats,
        }


# Define the main singing task
singing_task = join(
    InfoPage(
        Markup(
            """
            <h3>Singing to Melodies</h3>
            <hr>
            In each trial, you will listen to a melody and be asked to sing it back as accurately as possible. 
            <br><br>
            <b><b>Remember</b></b>: Sing each note clearly to the syllable 'TA' and leave short gaps between notes.
            <hr>
            """
            ),
        time_estimate=5,
    ),
    StaticTrialMaker(
            id_="static_singing_trialmaker",
            trial_class=SingingTrial,
            nodes=nodes,
            expected_trials_per_participant=TRIALS_PER_PARTICIPANT,
            max_trials_per_participant=TRIALS_PER_PARTICIPANT,
            recruit_mode="n_participants",
            allow_repeated_nodes=False,
            n_repeat_trials=N_REPEAT_TRIALS,
            balance_across_nodes=True,
            target_n_participants=NUM_PARTICIPANTS,
            check_performance_at_end=False,
        ),
    )


########################################################################################################################
# Timeline
########################################################################################################################

# Define the experiment timeline
class Exp(psynet.experiment.Experiment):
    label = "Static singing experiment demo"
    asset_storage = DebugStorage()  # Use DebugStorage for testing; switch to LocalStorage for real experiments

    if USE_SING_PRESCREENS:
        timeline = Timeline(
            NoConsent(),  # Consent form
            mic_test(),  # Microphone test
            tonejs_volume_test(TIMBRE, note_duration_tonejs, note_silence_tonejs),  # Volume test
            InfoPage("Next, you will perform a series of singing exercises to make sure we can record your voice.", time_estimate=2),
            recording_example(),  # Example recording task
            singing_performance(),  # Singing performance test
            # Automatically assign register based on predicted register from singing performance
            conditional(
                label="assign_register",
                condition=lambda experiment, participant: participant.var.predicted_register == "undefined",
                logic_if_true=CodeBlock(
                    lambda experiment, participant: participant.var.set(
                        "register", random.choice(["low", "high"]))
                ),
                logic_if_false=CodeBlock(lambda experiment, participant: participant.var.set(
                    "register",participant.var.predicted_register)
                                         ),
                fix_time_credit=False
            ),
            singing_task,  # Main singing task
        )
    else:
        timeline = Timeline(
            NoConsent(),  # Consent form
            # Since we don't use singing_performance, we need to set the register manually (set either to "low" or "high")
            CodeBlock(lambda participant: participant.var.set("register", "low")),
            singing_task,  # Main singing task
        )
