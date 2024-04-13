import random

import numpy as np
import soundfile as sf

import psynet.experiment
from psynet.asset import FastFunctionAsset
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.staircase import StaircaseNode, StaircaseTrial, StaircaseTrialMaker
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class PitchDiscriminationNode(StaircaseNode):
    k = 2  # 2 up 1 down procedure
    step = 0.5  # going up one difficulty level means halving the interval

    def increase_difficulty(self):
        # Smaller pitch differences are harder
        self.parameter *= self.step

    def decrease_difficulty(self):
        # Larger pitch differences are easier
        self.parameter /= self.step


def nodes():
    return [
        StaircaseNode(
            parameter=1,  # discrimination interval in semitones
        )
    ]


class PitchDiscriminationTrial(StaircaseTrial):
    time_estimate = 5

    def finalize_definition(self, definition, experiment, participant):
        parameter = definition["parameter"]
        correct_answer = random.choice(["First", "Second"])
        lower_pitch = 60  # MIDI note number

        higher_pitch = lower_pitch + parameter

        # The participant is asked, "Which pitch is higher?
        if correct_answer == "First":
            pitches = [higher_pitch, lower_pitch]
        else:
            pitches = [lower_pitch, higher_pitch]

        frequencies = [440 * 2 ** ((pitch - 69) / 12) for pitch in pitches]

        definition.update(
            {
                "correct_answer": correct_answer,
                "pitches": pitches,
                "frequencies": frequencies,
            }
        )

        self.add_assets(
            {
                "stimulus": FastFunctionAsset(
                    function=self.synth_stimulus,
                    extension=".wav",
                )
            }
        )

        return definition

    sample_rate = 44100
    tone_duration = 1.0
    silence_duration = 0.5
    rise_time = 0.25

    def synth_stimulus(self, path, frequencies):
        # Synthesize two tones one after the other, each of length 1 second,
        # with the specified frequencies
        waveform = np.concatenate(
            [
                self.make_tone(frequencies[0], duration=self.silence_duration),
                self.make_silence(duration=self.silence_duration),
                self.make_tone(frequencies[1], duration=self.silence_duration),
            ]
        )

        sf.write(path, waveform, 44100)

    def make_tone(self, frequency, duration):
        n_samples = int(duration * self.sample_rate)
        signal = np.cos(2 * np.pi * frequency * np.arange(n_samples) / self.sample_rate)
        envelope = np.ones(len(signal))
        n_rise_samples = round(self.rise_time * self.sample_rate)
        envelope[:n_rise_samples] = np.linspace(start=0, stop=1, num=n_rise_samples)
        envelope[-n_rise_samples:] = np.linspace(start=1, stop=0, num=n_rise_samples)
        return signal * envelope

    def make_silence(self, duration):
        n_samples = round(duration * self.sample_rate)
        return np.zeros(n_samples)

    def show_trial(self, experiment, participant):
        return ModularPage(
            "pitch_discrimination_trial",
            AudioPrompt(self.assets["stimulus"], "Which pitch was higher?"),
            PushButtonControl(
                choices=["First", "Second"],
                arrange_vertically=False,
            ),
            time_estimate=self.time_estimate,
        )

    def score_answer(self, answer, definition):
        return int(answer == definition["correct_answer"])


class Exp(psynet.experiment.Experiment):
    label = "Pitch discrimination demo"

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            """
            In each trial you will hear two tones. One will be higher in pitch than the other.
            Your task is to identify which tone is the highest.
            """,
            time_estimate=5,
        ),
        StaircaseTrialMaker(
            id_="pitch_discrimination",
            trial_class=PitchDiscriminationTrial,
            node_class=PitchDiscriminationNode,
            chain_type="within",
            expected_trials_per_participant=20,
            max_trials_per_participant=20,
            max_nodes_per_chain=20,
            start_nodes=nodes,
            target_n_participants=1,
        ),
        SuccessfulEndPage(),
    )
