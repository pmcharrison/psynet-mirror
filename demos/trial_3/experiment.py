import random

import psynet.experiment
from psynet.asset import (  # noqa
    CachedFunctionAsset,
    DebugStorage,
    FastFunctionAsset,
    S3Storage,
)
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline, for_loop
from psynet.trial.main import Trial

from .custom_synth import synth_prosody


def synth_stimulus(path, frequency_gradient, start_frequency):
    frequencies = [start_frequency + i * frequency_gradient for i in range(5)]
    synth_prosody(vector=frequencies, output_path=path)


class RateTrial(Trial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "audio_rating",
            AudioPrompt(
                self.assets["audio"],
                text="How happy is the following word?",
            ),
            PushButtonControl(
                ["Not at all", "A little", "Very much"],
            ),
        )


class Exp(psynet.experiment.Experiment):
    label = "Simple trial demo (3)"

    timeline = Timeline(
        NoConsent(),
        for_loop(
            "Deliver 5 trials with randomly sampled parameters",
            [
                {
                    "frequency_gradient": random.uniform(-100, 100),
                    "start_frequency": random.uniform(-100, 100),
                }
                for _ in range(5)
            ],
            lambda definition: RateTrial.cue(
                definition,
                assets={
                    "audio": FastFunctionAsset(
                        function=synth_stimulus,
                        extension=".wav",
                    ),
                },
            ),
            time_estimate_per_iteration=RateTrial.time_estimate,
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.trials()) == 5
