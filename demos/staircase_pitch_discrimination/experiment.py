import random

import numpy as np
import soundfile as sf

import psynet.experiment
from psynet.asset import FastFunctionAsset
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.staircase import (
    GeometricStaircaseNode,
    GeometricStaircaseRun,
    GeometricStaircaseTrial,
    GeometricStaircaseTrialMaker,
)
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class PitchDiscriminationNode(GeometricStaircaseNode):
    k = 2  # 2 up 1 down procedure
    step = 0.5  # going up one difficulty level means halving the interval

    def increase_difficulty(self):
        # Smaller pitch differences are harder
        self.parameter *= self.step

    def decrease_difficulty(self):
        # Larger pitch differences are easier
        self.parameter /= self.step


class PitchDiscriminationTrial(GeometricStaircaseTrial):
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
                bot_response=self.get_bot_response,
            ),
            time_estimate=self.time_estimate,
        )

    bot_threshold = 0.125

    def get_bot_response(self, bot: Bot):
        # We imagine the bot has the discrimination threshold specified below.
        # We suppose they always respond correctly if the stimulus parameter is
        # above the threshold, and always respond incorrectly if it is below.
        # This is unrealistic (normally they would respond by chance if it is below),
        # but it allows us to produce a better automated test.
        bot_threshold = 0.125
        responds_correctly = self.parameter >= bot_threshold
        if responds_correctly:
            return self.definition["correct_answer"]
        else:
            if self.definition["correct_answer"] == "First":
                return "Second"
            else:
                return "First"

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
        GeometricStaircaseTrialMaker(
            id_="pitch_discrimination",
            trial_class=PitchDiscriminationTrial,
            node_class=PitchDiscriminationNode,
            start_parameter=1.0,
            n_runs=2,
            max_trials_per_run=30,
            max_reversals_per_run=6,
            expected_trials_per_participant=20,
            target_n_participants=1,
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        step = PitchDiscriminationNode.step
        bot_threshold = PitchDiscriminationTrial.bot_threshold
        max_reversals_per_run = self.timeline.get_trial_maker(
            "pitch_discrimination"
        ).max_reversals_per_run

        runs = GeometricStaircaseRun.query.filter_by(participant_id=bot.id).all()

        for run in runs:
            assert len(run.all_trials) > max_reversals_per_run

        for trial in runs[1].all_trials:
            assert trial.id > max(
                [t.id for t in runs[0].all_trials]
            ), "Runs 0 and 1 were unexpectedly mixed"

        for run in runs:
            n_reversals = sum([node.reversal for node in run.nodes])
            assert n_reversals == max_reversals_per_run

            n = 4
            last_n_trials = run.all_trials[-n:]
            last_n_parameters = [
                trial.definition["parameter"] for trial in last_n_trials
            ]

            for parameter in last_n_parameters:
                assert (
                    bot_threshold * step <= parameter <= bot_threshold / step
                ), "Procedure did not converge to bot threshold"

            assert (
                bot_threshold * step <= run.mean_reversal_score <= bot_threshold / step
            ), f"Mean reversal score seems incorrect: {run.mean_reversal_score}"
