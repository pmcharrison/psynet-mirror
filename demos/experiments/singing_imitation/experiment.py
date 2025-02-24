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

# experiment
from .pre_screens import (
    tonejs_volume_test,
    mic_test,
    recording_example,
    singing_performance
)

# sing4me
from sing4me import singing_extract as sing
from . sing import melodies
from . sing.params import singing_2intervals


########################################################################################################################
# Global parameters
########################################################################################################################

USE_SING_PRESCREENS = False # if True, all singing prescreens are presented before the main singing tasks, including volumne test and a singing perforamcne test

TIME_ESTIMATE_TRIAL = 10
NUM_PARTICIPANTS = 10
NUM_MELODIES = 3  # this is the total number of stimuli/ nodes
TRIALS_PER_PARTICIPANT = NUM_MELODIES  # in this experiment num nodes is the same as num trials per participant

N_REPEAT_TRIALS = 0
INITIAL_RECRUIT_SIZE = 20
SAVE_PLOT = True

# singing
roving_width = 2.5
roving_mean = dict(
    default=55,
    low=49,
    high=61
)

NUM_NOTES = 5
NUM_INT = NUM_NOTES - 1
SYLLABLE = "TA"
TIME_AFTER_SINGING = 1

REFERENCE_MODE = "pitch_mode"  # pitch_mode vs previous_note vs first_note
MAX_ABS_INT_ERROR_ALLOWED = 5.5  # set to 999 if NUM_INT > 2
MAX_INT_SIZE = 999
MAX_MELODY_PITCH_RANGE = 999  # deactivated
MAX_INTERVAL2REFERENCE = 10  # set to 7.5 if NUM_INT > 2
NUM_CHAINS_EXPERIMENT = 200  # decrease if NUM_INT > 2
NUM_TRIALS_PARTICIPANT = 40  # decrease if NUM_INT > 2

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
pitch_duration = note_duration_tonejs + note_silence_tonejs


# durations
def estimate_time_per_trial(
        # estimate time for trials: melody and singing duration
        pitch_duration,
        num_pitches,
        time_after_singing
):
    melody_duration = pitch_duration * num_pitches
    singing_duration = melody_duration + time_after_singing
    return melody_duration, singing_duration


melody_duration, singing_duration = estimate_time_per_trial(
    pitch_duration,
    (NUM_NOTES + 1),
    TIME_AFTER_SINGING
)


########################################################################################################################
# Stimuli
########################################################################################################################
# This is how we generate melodies based on a reference_pitch, max_interval2reference, and number of notes
def generate_random_melody(mel_id, roving_mean, roving_width, max_interval2reference, num_notes):
    # sample reference pitch
    reference_pitch = melodies.sample_reference_pitch(
        roving_mean,
        roving_width,
    )
    # sample pitches
    target_pitches = melodies.sample_absolute_pitches(
        reference_pitch=reference_pitch,
        max_interval2reference=max_interval2reference,
        num_pitches=num_notes
    )
    # get intervals
    target_intervals = melodies.convert_absolute_pitches_to_interval_sequence(target_pitches, "previous_note")
    # get intervals from pitch to reference pitch
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

nodes = [
    StaticNode(
        definition={
            "melody": generate_random_melody(i, roving_mean["high"], roving_width, MAX_INTERVAL2REFERENCE, NUM_NOTES)
        },
    )
    for i in range(1, (NUM_MELODIES + 1))
]


########################################################################################################################
# experiment parts
########################################################################################################################
class SingingTrial(AudioRecordTrial, StaticTrial):
    time_estimate = TIME_ESTIMATE_TRIAL

    def show_trial(self, experiment, participant):

        melody = self.definition

        # convert to right register
        if self.participant.var.register == "high":
            target_pitches = melody['melody']['target_pitches']
        else:
            target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]

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

        # convert to right register
        if self.participant.var.register == "high":
            target_pitches =  melody['melody']['target_pitches']
            reference_pitch =  melody['melody']['reference_pitch']
        else:
            target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]
            reference_pitch = melody['melody']['reference_pitch'] - 12

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
            MAX_INT_SIZE,  # only used in interval representation, currently deactivated
            MAX_MELODY_PITCH_RANGE,  # only used in interval representation, currently deactivated
            REFERENCE_MODE,
            stats,
            MAX_ABS_INT_ERROR_ALLOWED,  # deactivated
            (MAX_INTERVAL2REFERENCE * 2)  # only used in pitch mode
        )

        failed = is_failed["failed"]
        reason = is_failed["reason"]

        # convert back to high register
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


singing_task = join(
    InfoPage(
        Markup(
            """
            <h3>Singing to Melodies</h3>
            <hr>
            In each trial, you will listen to a melody and asked to sing it back as accurately as possible. 
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

class Exp(psynet.experiment.Experiment):
    label = "Static singing experiment demo"
    asset_storage = DebugStorage()


    if USE_SING_PRESCREENS:
        timeline = Timeline(
            NoConsent(),  # add consent
            mic_test(),
            tonejs_volume_test(TIMBRE, note_duration_tonejs, note_silence_tonejs),
            InfoPage("Next, you will perform a series of singing exercises to make sure we can record your voice.", time_estimate=2),
            recording_example(),
            singing_performance(),
            # we automatically assign register based on the predicted_register obtained from singing_performance
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
            # You can use the line below to set the register manually (useful to debug and avoid the singing_performance)
            # CodeBlock(lambda participant: participant.var.set("register", "low")),
            singing_task,
            SuccessfulEndPage(),
        )
    else:
        timeline = Timeline(
            NoConsent(),  # add consent
            # Since we don't use singing_performance, we need to set the register manually (set either to "low" or "high")
            CodeBlock(lambda participant: participant.var.set("register", "low")),
            singing_task,
            SuccessfulEndPage(),
        )

