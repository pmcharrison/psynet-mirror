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
from psynet.trial.static import Stimulus, StimulusSet

from .custom_synth import synth_prosody

##########################################################################################
# Stimuli
##########################################################################################


def synth_stimulus(path, frequencies):
    synth_prosody(vector=frequencies, output_path=path)


stimulus_set = StimulusSet(
    "rating_stimuli",
    [
        Stimulus(
            definition={
                "frequency_gradient": frequency_gradient,
                "start_frequency": start_frequency,
                "frequencies": [
                    start_frequency + i * frequency_gradient for i in range(5)
                ],
            },
        )
        for frequency_gradient in [-100, -50, 0, 50, 100]
        for start_frequency in [-100, 0, 100]
    ],
)


class RateTrial(Trial):
    time_estimate = 5

    def show_trial(self, experiment, participant):
        return ModularPage(
            "audio_rating",
            AudioPrompt(
                self.stimulus.assets["audio"],
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
            random.sample(stimulus_set.keys(), 5),
            lambda key, stimuli: RateTrial.cue(
                stimuli["rating_stimuli"][key],
                assets={
                    "audio": FastFunctionAsset(
                        function=synth_stimulus,
                        extension=".wav",
                    ),
                },
            ),
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.trials()) == 5
